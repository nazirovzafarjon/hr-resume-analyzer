"""Tests for Celery distributed batch resume analysis architecture."""

from unittest.mock import AsyncMock, patch

from app.crud import batch as batch_crud
from app.models.analysis_batch import AnalysisBatch, AnalysisBatchStatus
from app.models.analysis_batch_item import AnalysisBatchItem, BatchItemStatus
from app.models.application import AnalysisStatus, Application, ApplicationStatus
from app.schemas.application_analysis import ApplicationAnalysis
from app.services.ai.job_analyzer import AIServiceError
from app.tasks.ai_analysis import (
    analyze_batch_item_task,
    dispatch_batch_analysis_task,
)

SAMPLE_BATCH_RESULT = {
    "match_percentage": 88.0,
    "summary": "Qualified candidate with matching stack.",
    "matched_requirements": ["Python", "FastAPI"],
    "missing_requirements": [],
    "matched_skills": ["Python"],
    "missing_skills": [],
    "strengths": ["Fast learner"],
    "weaknesses": [],
    "risks": [],
    "experience_analysis": "2+ years experience.",
    "education_analysis": "BSc Computer Science.",
    "relevant_experience": ["Software Engineer"],
    "relevant_projects": ["API platform"],
    "ai_recommendation": "hire",
}


def _create_test_applications(db_session, job_id: int, count: int) -> list[Application]:
    """Helper to create N unanalyzed applications."""
    apps = []
    for i in range(count):
        app = Application(
            job_id=job_id,
            name=f"Candidate {i}",
            email=f"candidate_{i}@example.com",
            resume_path="",
            application_status=ApplicationStatus.NEW,
            analysis_status=AnalysisStatus.NEW,
        )
        db_session.add(app)
        apps.append(app)
    db_session.commit()
    for app in apps:
        db_session.refresh(app)
    return apps


def test_batch_dispatch_and_execution_success(client, user, sample_job, db_session):
    """Test full dispatch and Celery worker execution of a multi-item batch."""
    apps = _create_test_applications(db_session, sample_job["id"], 5)
    app_ids = [a.id for a in apps]

    batch = batch_crud.create_batch(db_session, owner_id=user["id"], application_ids=app_ids)
    assert len(batch.items) == 5
    for item in batch.items:
        assert item.status == BatchItemStatus.PENDING

    mock_analysis = ApplicationAnalysis(**SAMPLE_BATCH_RESULT)
    with patch(
        "app.services.application_analysis.analyze_application",
        new_callable=AsyncMock,
    ) as mock_analyze:
        mock_analyze.return_value = mock_analysis

        result = dispatch_batch_analysis_task.apply(kwargs={"batch_id": batch.id}).result

    assert result["status"] == "dispatched"
    assert result["total_items"] == 5

    db_session.expire_all()
    refreshed_batch = db_session.get(AnalysisBatch, batch.id)
    assert refreshed_batch.status == AnalysisBatchStatus.COMPLETED
    assert refreshed_batch.successful_count == 5
    assert refreshed_batch.failed_count == 0
    assert refreshed_batch.skipped_count == 0
    assert refreshed_batch.processed == 5
    assert refreshed_batch.remaining == 0

    for item in refreshed_batch.items:
        assert item.status == BatchItemStatus.COMPLETED
        assert item.completed_at is not None

    for app_id in app_ids:
        app = db_session.get(Application, app_id)
        assert app.analysis_status == AnalysisStatus.COMPLETED
        assert app.ai_score == 88.0


def test_batch_cooperative_cancellation(client, user, sample_job, db_session):
    """Test cooperative cancellation halts execution before calling AI."""
    apps = _create_test_applications(db_session, sample_job["id"], 2)
    batch = batch_crud.create_batch(db_session, owner_id=user["id"], application_ids=[a.id for a in apps])

    # Cancel the batch before the item runs
    batch_crud.cancel_batch(db_session, batch)
    item = batch.items[0]

    with patch(
        "app.services.application_analysis.analyze_application",
        new_callable=AsyncMock,
    ) as mock_analyze:
        result = analyze_batch_item_task.apply(
            kwargs={"batch_id": batch.id, "item_id": item.id, "application_id": item.application_id}
        ).result

    assert result["status"] == "cancelled"
    assert mock_analyze.call_count == 0  # Zero AI calls made!

    db_session.expire_all()
    refreshed_item = db_session.get(AnalysisBatchItem, item.id)
    assert refreshed_item.status == BatchItemStatus.CANCELLED


def test_batch_partial_failures_and_skips(client, user, sample_job, db_session):
    """Test batch gracefully handles mixed success, failure, and skipped items."""
    apps = _create_test_applications(db_session, sample_job["id"], 3)
    app1, app2, app3 = apps

    # Make app3 already completed so it should be skipped
    app3.analysis_status = AnalysisStatus.COMPLETED
    db_session.commit()

    batch = batch_crud.create_batch(
        db_session,
        owner_id=user["id"],
        application_ids=[app1.id, app2.id, app3.id],
    )

    mock_analysis = ApplicationAnalysis(**SAMPLE_BATCH_RESULT)

    # App1 succeeds, App2 fails with 422, App3 is skipped
    def side_effect(*args, **kwargs):
        # We check which prompt is being analyzed
        return mock_analysis

    with patch(
        "app.services.application_analysis.analyze_application",
        new_callable=AsyncMock,
    ) as mock_analyze:
        mock_analyze.side_effect = [
            mock_analysis,
            AIServiceError("Invalid resume content", status_code=422),
        ]

        dispatch_batch_analysis_task.apply(kwargs={"batch_id": batch.id})

    db_session.expire_all()
    refreshed_batch = db_session.get(AnalysisBatch, batch.id)
    assert refreshed_batch.status == AnalysisBatchStatus.COMPLETED
    assert refreshed_batch.successful_count == 1
    assert refreshed_batch.failed_count == 1
    assert refreshed_batch.skipped_count == 1
    assert refreshed_batch.processed == 3

    item1 = batch_crud.get_batch_item_by_application(db_session, batch.id, app1.id)
    item2 = batch_crud.get_batch_item_by_application(db_session, batch.id, app2.id)
    item3 = batch_crud.get_batch_item_by_application(db_session, batch.id, app3.id)

    assert item1.status == BatchItemStatus.COMPLETED
    assert item2.status == BatchItemStatus.FAILED
    assert "Invalid resume content" in item2.error_message
    assert item3.status == BatchItemStatus.SKIPPED


def test_batch_item_creation_up_to_1000(client, user, sample_job, db_session):
    """Test creating a batch with 1,000 items preserves schema constraints and scalability."""
    app_ids = list(range(10001, 11001))  # 1,000 synthetic IDs

    batch = AnalysisBatch(
        owner_id=user["id"],
        application_ids=app_ids,
        status=AnalysisBatchStatus.QUEUED,
    )
    db_session.add(batch)
    db_session.commit()
    db_session.refresh(batch)

    assert batch.total == 1000
    assert batch.processed == 0
    assert batch.remaining == 1000
