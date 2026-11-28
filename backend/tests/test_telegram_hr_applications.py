"""Telegram bot phase 8: HR application lists, resume, form answers and AI analysis."""

import uuid
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from app.bot import actions
from app.core.config import settings
from app.core.database import SessionLocal
from app.models.analysis_batch import AnalysisBatch
from app.models.application import AnalysisStatus, Application, ApplicationStatus
from app.models.application_form import ApplicationResponse
from app.models.audit_log import AuditLog
from app.models.telegram_link import TelegramAccountKind, TelegramLink
from app.schemas.application_analysis import ApplicationAnalysis
from tests.test_telegram_hr_notifications import (
    HR_TG,
    OTHER_TG,
    _add_application,
    _create_job,
    _link_hr,
    _profile,
)

ANALYSIS = {
    "match_percentage": 87.4,
    "summary": "Strong backend profile.",
    "strengths": ["Python", "FastAPI <APIs>"],
    "missing_requirements": ["Kubernetes"],
    "risks": ["Short tenures"],
    "ai_recommendation": "hire",
    "resume_text_available": True,
}


@pytest.fixture
def telegram_on(monkeypatch):
    monkeypatch.setattr(settings, "TELEGRAM_ENABLED", True)
    monkeypatch.setattr(settings, "TELEGRAM_BOT_TOKEN", "123:test-token")
    monkeypatch.setattr(settings, "TELEGRAM_BOT_USERNAME", "ra_test_bot")


@pytest.fixture
def sent(monkeypatch):
    from app.services.telegram import client as tg_client

    messages: list[dict] = []

    def fake_send(chat_id, text, *, buttons=None):
        messages.append({"chat_id": chat_id, "text": text, "buttons": buttons or []})
        return {"message_id": len(messages)}

    monkeypatch.setattr(tg_client, "send_message", fake_send)
    return messages


@pytest.fixture
def hr(user, telegram_on):
    _link_hr(user["id"])
    return user


@pytest.fixture
def job(client, user):
    return _create_job(client, user["headers"])


def _callbacks(reply):
    return [button["callback_data"] for row in reply.buttons for button in row if "callback_data" in button]


def _set(application_id, **fields):
    with SessionLocal() as db:
        application = db.get(Application, application_id)
        for key, value in fields.items():
            setattr(application, key, value)
        db.commit()


def _completed(application_id, **overrides):
    _set(
        application_id,
        analysis_status=AnalysisStatus.COMPLETED,
        ai_score=ANALYSIS["match_percentage"],
        ai_analysis_details=dict(ANALYSIS, **overrides),
    )


# --- lists -----------------------------------------------------------------------


def test_list_filters_by_status(hr, job):
    _add_application(job["id"], name="Fresh")
    _add_application(job["id"], name="Picked", status=ApplicationStatus.SHORTLISTED)

    new = actions.hr_list(_profile(), "new")
    assert "Fresh" in new.text and "Picked" not in new.text
    shortlisted = actions.hr_list(_profile(), "shortlisted")
    assert "Picked" in shortlisted.text and "Fresh" not in shortlisted.text
    everything = actions.hr_list(_profile(), "all")
    assert "Fresh" in everything.text and "Picked" in everything.text
    # The mixed list names each status.
    assert "Tanlangan" in everything.text

    callbacks = _callbacks(new)
    for key in actions.HR_FILTERS:
        assert f"hr:ls:{key}:0:0" in callbacks
    assert "hr:jobs:new" in callbacks and "hr:find" in callbacks
    assert "• Yangi" in str(new.buttons)


def test_list_by_job(client, user, hr, job):
    other_job = _create_job(client, user["headers"], position="Designer")
    _add_application(job["id"], name="Backend person")
    _add_application(other_job["id"], name="Design person")

    reply = actions.hr_list(_profile(), "all", other_job["id"])
    assert "Design person" in reply.text and "Backend person" not in reply.text
    assert "💼 Designer" in reply.text
    assert f"hr:ls:new:{other_job['id']}:0" in _callbacks(reply)

    picker = actions.hr_jobs_picker(_profile(), "all")
    assert f"hr:ls:all:{other_job['id']}:0" in _callbacks(picker)
    assert "hr:ls:all:0:0" in _callbacks(picker)


def test_list_ignores_another_hrs_job(client, hr, other_user, job):
    foreign = _create_job(client, other_user["headers"])
    _add_application(foreign["id"], name="Not yours")
    _add_application(job["id"], name="Yours")
    reply = actions.hr_list(_profile(), "all", foreign["id"])
    assert "Not yours" not in reply.text and "Yours" in reply.text


def test_list_shows_ai_score_and_pages(hr, job):
    ids = [_add_application(job["id"], name=f"Person {n}") for n in range(7)]
    _completed(ids[-1])
    first = actions.hr_list(_profile(), "new")
    assert "(7 ta) — 1/2" in first.text and "🤖 87%" in first.text
    assert "hr:ls:new:0:1" in _callbacks(first)


def test_search_by_name_or_email(hr, job):
    _add_application(job["id"], name="Aziza Karimova")
    _add_application(job["id"], name="Bob")
    reply = actions.hr_search(_profile(), "  karim ")
    assert "Aziza Karimova" in reply.text and "Bob" not in reply.text
    assert "Qidiruv: «karim»" in reply.text
    assert "hr:ls:all:0:0" in _callbacks(reply)
    assert actions.hr_search(_profile(), "a").awaiting_input
    assert actions.hr_search_prompt(_profile()).awaiting_input


def test_search_escapes_html(hr, job):
    _add_application(job["id"], name="<b>Eve</b>")
    reply = actions.hr_search(_profile(), "<b>")
    assert "&lt;b&gt;Eve&lt;/b&gt;" in reply.text


def test_search_treats_wildcards_literally(hr, job):
    _add_application(job["id"], name="Ann_Lee")
    _add_application(job["id"], name="Annxlee")
    reply = actions.hr_search(_profile(), "n_l")
    assert "Ann_Lee" in reply.text and "Annxlee" not in reply.text
    assert "Ann_Lee" not in actions.hr_search(_profile(), "%%").text


def test_start_home_screen_offers_quick_actions(hr):
    text = actions.start(_profile(), None)
    assert "Assalomu alaykum" in text
    callbacks = [button["callback_data"] for row in actions.home_buttons(_profile()) for button in row]
    assert callbacks == ["hr:ls:all:0:0", "hr:new:0", "hr:jl:0", "hr:ivl:today:0", "hr:st:7d", "cfg:open"]


def test_applications_entry_for_hr_and_candidate(client, hr, job):
    from tests.test_telegram_notifications import _link, _register_candidate

    _add_application(job["id"], name="Someone")
    reply = actions.applications_entry(_profile())
    assert "Arizalar: Hammasi" in reply.text
    assert "apps:0" not in _callbacks(reply)

    candidate_id = _register_candidate(client, "both@example.com")
    _link(candidate_id, telegram_user_id=HR_TG)
    assert "apps:0" in _callbacks(actions.applications_entry(_profile()))


def test_applications_entry_for_candidate_only(client, telegram_on):
    from tests.test_telegram_notifications import _link, _register_candidate

    _link(_register_candidate(client, "c@example.com"), telegram_user_id=HR_TG)
    assert "Hali ariza" in actions.applications_entry(_profile()).text


def test_lists_require_an_hr_link(telegram_on):
    assert "HR uchun" in actions.hr_list(_profile()).text
    assert "HR uchun" in actions.hr_jobs_picker(_profile()).text
    assert "HR uchun" in actions.hr_search_prompt(_profile()).text


# --- the card ----------------------------------------------------------------------


def test_card_offers_resume_form_and_analysis(hr, job):
    application_id = _add_application(job["id"])
    callbacks = _callbacks(actions.hr_application_detail(_profile(), application_id, page=2))
    assert f"hr:cv:{application_id}:2" in callbacks
    assert f"hr:fa:{application_id}:2" in callbacks
    assert f"hr:ai:{application_id}:2" in callbacks
    assert callbacks[-1] == "hr:back:2"

    _completed(application_id)
    callbacks = _callbacks(actions.hr_application_detail(_profile(), application_id))
    assert f"hr:aix:{application_id}:0" in callbacks and f"hr:air:{application_id}:0" in callbacks
    assert f"hr:ai:{application_id}:0" not in callbacks

    _set(application_id, analysis_status=AnalysisStatus.ANALYZING)
    callbacks = _callbacks(actions.hr_application_detail(_profile(), application_id))
    assert not any(c.startswith(("hr:ai:", "hr:air:", "hr:aix:")) for c in callbacks)


# --- resume and form answers ------------------------------------------------------------


def test_resume_is_sent_as_a_document(hr, job):
    directory = Path(settings.UPLOAD_DIR) / "resumes"
    directory.mkdir(parents=True, exist_ok=True)
    name = f"{uuid.uuid4().hex}.pdf"
    (directory / name).write_bytes(b"%PDF-1.4 test")
    application_id = _add_application(job["id"], name="Jane Doe")
    _set(application_id, resume_path=f"resumes/{name}")

    reply = actions.hr_resume(_profile(), application_id)
    path, filename = reply.document
    assert Path(path).read_bytes() == b"%PDF-1.4 test"
    assert filename == "Jane Doe - CV.pdf"
    assert "Jane Doe" in reply.text


def test_missing_resume_is_explained(hr, job):
    application_id = _add_application(job["id"])
    reply = actions.hr_resume(_profile(), application_id)
    assert reply.document is None and "topilmadi" in reply.text


def test_resume_of_another_hr_is_not_sent(client, hr, other_user, job):
    _link_hr(other_user["id"], telegram_user_id=OTHER_TG)
    application_id = _add_application(job["id"])
    reply = actions.hr_resume(_profile(OTHER_TG), application_id)
    assert reply.document is None and "topilmadi" in reply.text


def test_form_answers(hr, job):
    application_id = _add_application(job["id"])
    with SessionLocal() as db:
        db.add(
            ApplicationResponse(
                application_id=application_id,
                responses=[
                    {"label": "Years of experience", "type": "number", "value": 4},
                    {"label": "Skills", "type": "multiselect", "value": ["Python", "SQL"]},
                    {"label": "Resume", "type": "file", "value": "resumes/x.pdf"},
                    {"label": "Why us?", "type": "textarea", "value": "<script>"},
                    {"label": "Remote ok", "type": "checkbox", "value": True},
                    {"label": "Portfolio", "type": "url", "value": ""},
                ],
            )
        )
        db.commit()

    reply = actions.hr_form_answers(_profile(), application_id, page=1)
    assert "<b>Years of experience</b>\n4" in reply.text
    assert "Python, SQL" in reply.text and "&lt;script&gt;" in reply.text
    assert "✓" in reply.text and "<b>Portfolio</b>\n—" in reply.text
    assert "resumes/x.pdf" not in reply.text
    assert _callbacks(reply) == [f"hr:app:{application_id}:1"]


def test_form_answers_when_there_are_none(hr, job):
    application_id = _add_application(job["id"])
    assert "javoblar yo'q" in actions.hr_form_answers(_profile(), application_id).text


# --- AI summary ---------------------------------------------------------------------


def test_analysis_summary(hr, job):
    application_id = _add_application(job["id"])
    _completed(application_id)
    reply = actions.hr_analysis_summary(_profile(), application_id, page=1)
    assert "87%" in reply.text and "Olish mumkin" in reply.text
    assert "Strong backend profile." in reply.text
    assert "• FastAPI &lt;APIs&gt;" in reply.text
    assert "• Kubernetes" in reply.text and "• Short tenures" in reply.text
    assert "Rezyume matnini o'qib bo'lmadi" not in reply.text
    assert _callbacks(reply) == [f"hr:air:{application_id}:1", f"hr:app:{application_id}:1"]


def test_analysis_summary_without_resume_text(hr, job):
    application_id = _add_application(job["id"])
    _completed(application_id, resume_text_available=False)
    assert "Rezyume matnini o'qib bo'lmadi" in actions.hr_analysis_summary(_profile(), application_id).text


def test_analysis_summary_before_analysis(hr, job):
    application_id = _add_application(job["id"])
    assert "hali tahlil qilinmagan" in actions.hr_analysis_summary(_profile(), application_id).text


# --- starting an analysis --------------------------------------------------------------


def _analyse(mock_return=None, side_effect=None):
    return patch(
        "app.services.application_analysis.analyze_application",
        new_callable=AsyncMock,
        return_value=mock_return,
        side_effect=side_effect,
    )


def test_start_analysis_runs_and_tells_hr(hr, job, sent):
    application_id = _add_application(job["id"], name="Jane Doe")
    with _analyse(ApplicationAnalysis(**ANALYSIS)) as mock:
        reply = actions.hr_start_analysis(_profile(), application_id, page=0)
    assert mock.call_count == 1
    assert "AI tahlili boshlandi" in reply.text

    with SessionLocal() as db:
        application = db.get(Application, application_id)
        assert application.analysis_status == AnalysisStatus.COMPLETED
        assert application.ai_score == 87.4

    [message] = [m for m in sent if "AI tahlili tugadi" in m["text"]]
    assert message["chat_id"] == HR_TG
    assert "Jane Doe" in message["text"] and "87%" in message["text"] and "Olish mumkin" in message["text"]
    assert message["buttons"][0][0]["callback_data"] == f"hr:aix:{application_id}:0"


def test_completed_analysis_is_not_rerun_without_force(hr, job, sent):
    application_id = _add_application(job["id"])
    _completed(application_id)
    with _analyse(ApplicationAnalysis(**ANALYSIS)) as mock:
        reply = actions.hr_start_analysis(_profile(), application_id)
        assert mock.call_count == 0
        assert "allaqachon tahlil qilingan" in reply.text
        actions.hr_start_analysis(_profile(), application_id, force=True)
        assert mock.call_count == 1


def test_running_analysis_is_not_started_twice(hr, job):
    from datetime import datetime, timezone

    application_id = _add_application(job["id"])
    _set(application_id, analysis_status=AnalysisStatus.ANALYZING, analysis_started_at=datetime.now(timezone.utc))
    with _analyse(ApplicationAnalysis(**ANALYSIS)) as mock:
        reply = actions.hr_start_analysis(_profile(), application_id)
    assert mock.call_count == 0 and "hozir tahlil qilinmoqda" in reply.text


def test_failed_analysis_tells_hr(hr, job, sent):
    from app.services.ai.job_analyzer import AIServiceError

    application_id = _add_application(job["id"])
    with _analyse(side_effect=AIServiceError("Provider is down", status_code=503)):
        actions.hr_start_analysis(_profile(), application_id)
    [message] = [m for m in sent if "amalga oshmadi" in m["text"]]
    assert message["chat_id"] == HR_TG


def test_analysis_switch_off_sends_nothing(hr, job, sent):
    with SessionLocal() as db:
        db.query(TelegramLink).filter_by(kind=TelegramAccountKind.HR).one().notify_analysis = False
        db.commit()
    application_id = _add_application(job["id"])
    with _analyse(ApplicationAnalysis(**ANALYSIS)):
        actions.hr_start_analysis(_profile(), application_id)
    assert not [m for m in sent if "AI tahlili" in m["text"]]


def test_analysis_without_provider(hr, job, monkeypatch):
    from app.services.ai import provider as ai_provider

    def missing(db, user_id):
        raise ai_provider.AIConfigurationRequiredError()

    monkeypatch.setattr(ai_provider, "resolve_for_user", missing)
    application_id = _add_application(job["id"])
    reply = actions.hr_start_analysis(_profile(), application_id)
    assert "AI provayder sozlanmagan" in reply.text
    with SessionLocal() as db:
        assert db.get(Application, application_id).analysis_status != AnalysisStatus.ANALYZING


def test_other_hr_cannot_start_an_analysis(client, hr, other_user, job):
    _link_hr(other_user["id"], telegram_user_id=OTHER_TG)
    application_id = _add_application(job["id"])
    with _analyse(ApplicationAnalysis(**ANALYSIS)) as mock:
        reply = actions.hr_start_analysis(_profile(OTHER_TG), application_id)
    assert mock.call_count == 0 and "topilmadi" in reply.text


def test_web_api_still_starts_analyses(client, user, job):
    application_id = _add_application(job["id"])
    with _analyse(ApplicationAnalysis(**ANALYSIS)):
        response = client.post(f"/api/applications/{application_id}/analyze", headers=user["headers"])
    assert response.status_code == 200, response.text
    with SessionLocal() as db:
        assert db.get(Application, application_id).analysis_status == AnalysisStatus.COMPLETED


# --- analysing the new ones in one batch ----------------------------------------------------


def test_bulk_analysis_asks_then_runs_and_summarises(hr, job, sent):
    for n in range(3):
        _add_application(job["id"], name=f"Person {n}")
    _add_application(job["id"], name="Reviewed", status=ApplicationStatus.REVIEWING)

    listing = actions.hr_list(_profile(), "new")
    assert "hr:aiall:0" in _callbacks(listing) and "(3)" in str(listing.buttons)

    ask = actions.hr_analyze_all(_profile(), 0)
    assert "3 ta yangi ariza" in ask.text
    assert _callbacks(ask)[0] == "hr:aiallok:0"

    with _analyse(ApplicationAnalysis(**ANALYSIS)) as mock:
        done = actions.hr_analyze_all(_profile(), 0, confirmed=True)
    assert "3 ta ariza AI tahliliga yuborildi" in done.text
    assert mock.call_count == 3

    with SessionLocal() as db:
        batch = db.query(AnalysisBatch).one()
        assert batch.successful_count == 3
        entry = db.query(AuditLog).filter(AuditLog.action == "AI_BATCH_STARTED").one()
        assert entry.details["via"] == "telegram"
    summaries = [m for m in sent if "Jami: 3" in m["text"]]
    assert len(summaries) == 1 and "Muvaffaqiyatli: 3" in summaries[0]["text"]
    # Batch items do not send one message each.
    assert not [m for m in sent if "👤" in m["text"] and "AI tahlili tugadi" in m["text"]]
    assert "hr:aiall:0" not in _callbacks(actions.hr_list(_profile(), "new"))


def test_bulk_analysis_with_nothing_to_do(hr, job):
    _add_application(job["id"], status=ApplicationStatus.REVIEWING)
    assert "qolmadi" in actions.hr_analyze_all(_profile(), 0, confirmed=True).text


# --- settings and texts --------------------------------------------------------------


def test_analysis_switch_in_settings(hr):
    reply = actions.toggle_setting(_profile(), "hr", "analysis")
    assert "🔕 AI tahlil natijalari" in reply.text


def test_texts_exist_in_every_language(hr, job):
    application_id = _add_application(job["id"])
    for lang, word in (("ru", "Резюме"), ("en", "Resume")):
        reply = actions.hr_application_detail(_profile(language_code=lang), application_id)
        assert word in str(reply.buttons)
    for lang, word in (("ru", "Заявки"), ("en", "Applications")):
        assert word in actions.hr_list(_profile(language_code=lang)).text
