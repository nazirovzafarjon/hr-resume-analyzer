"""Candidate Portal business logic: what a candidate may see, and how.

Everything a candidate reads is derived here from the HR-owned data and built
into explicit ``schemas.candidate`` responses. Three concepts stay separate,
exactly as in the HR model:

* **Application status** — ``candidate_status()`` maps the HR pipeline
  (``ApplicationStatus`` + interviews + AI progress) to friendly,
  candidate-facing states. Internal terms ("shortlisted") never leave here.
* **AI analysis** — ``ai_feedback()`` exposes a sanitized compatibility view.
* **Interviews** — ``interview_view()`` without interviewer notes.

TODO(FUTURE): candidate <-> HR messaging, an AI assistant and notifications
should be their own modules that reference ``Application`` rather than extend
the status logic here; interview confirmation / rescheduling can extend
``Interview`` (e.g. a candidate response field) and ``interview_view()``.
"""

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.crud import application as application_crud
from app.crud import interview as interview_crud
from app.models.application import AnalysisStatus, Application, ApplicationStatus
from app.models.candidate_account import CandidateAccount
from app.models.interview import Interview, InterviewStatus
from app.schemas.candidate import (
    CandidateAIFeedback,
    CandidateAnalysisState,
    CandidateAnswer,
    CandidateApplicationDetail,
    CandidateApplicationSummary,
    CandidateDashboard,
    CandidateInterview,
    CandidateInterviewState,
    CandidateJob,
    CandidateStatus,
    TimelineStep,
    TimelineStepState,
)
from app.services.application_analysis import stored_analysis

#: HR statuses that end the application (the candidate's "completed" count).
_FINAL_STATUSES = {ApplicationStatus.HIRED, ApplicationStatus.REJECTED, ApplicationStatus.WITHDRAWN}
_FINAL_OUTCOME = {
    ApplicationStatus.HIRED: "accepted",
    ApplicationStatus.REJECTED: "rejected",
    ApplicationStatus.WITHDRAWN: "withdrawn",
}


def _aware(value: datetime | None) -> datetime | None:
    if value is not None and value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _upcoming(interviews: list[Interview]) -> list[Interview]:
    return sorted(
        (i for i in interviews if i.status == InterviewStatus.UPCOMING),
        key=lambda i: _aware(i.scheduled_at),
    )


def _completed(interviews: list[Interview]) -> list[Interview]:
    return sorted(
        (i for i in interviews if i.status == InterviewStatus.COMPLETED),
        key=lambda i: _aware(i.scheduled_at),
    )


# ---------------------------------------------------------------------------
# Status, AI, interviews
# ---------------------------------------------------------------------------


def candidate_status(application: Application) -> CandidateStatus:
    """The friendly, candidate-facing status of an application."""
    status = application.application_status
    if status == ApplicationStatus.WITHDRAWN:
        return CandidateStatus.WITHDRAWN
    if status == ApplicationStatus.REJECTED:
        return CandidateStatus.REJECTED
    if status == ApplicationStatus.HIRED:
        return CandidateStatus.ACCEPTED
    interviews = application.interviews or []
    if _upcoming(interviews):
        return CandidateStatus.INTERVIEW_SCHEDULED
    if _completed(interviews):
        return CandidateStatus.DECISION_PENDING
    if status == ApplicationStatus.INTERVIEW:
        return CandidateStatus.INTERVIEW_INVITED
    if status in (ApplicationStatus.REVIEWING, ApplicationStatus.SHORTLISTED):
        return CandidateStatus.HR_REVIEW
    if application.analysis_status == AnalysisStatus.ANALYZING:
        return CandidateStatus.AI_REVIEW
    return CandidateStatus.SUBMITTED


def analysis_state(application: Application) -> CandidateAnalysisState:
    return {
        AnalysisStatus.ANALYZING: CandidateAnalysisState.ANALYZING,
        AnalysisStatus.COMPLETED: CandidateAnalysisState.ANALYZED,
        AnalysisStatus.FAILED: CandidateAnalysisState.FAILED,
    }.get(application.analysis_status, CandidateAnalysisState.NOT_ANALYZED)


def ai_feedback(application: Application) -> CandidateAIFeedback:
    """Candidate-safe view of the stored AI analysis.

    IMPORTANT: candidate-facing AI feedback must stay sanitized. Only short
    skill/requirement lists and the match percentage are copied. Never add the
    HR recommendation (``ai_recommendation``), the recruiter-oriented free text
    (summary, strengths/weaknesses, risks, experience/education notes), the
    internal ``ai_score``, provider errors, prompts or anything about other
    applicants.
    """
    state = analysis_state(application)
    analysis = stored_analysis(application) if state == CandidateAnalysisState.ANALYZED else None
    if analysis is None:
        # A completed status with an unreadable payload shows as "not analysed".
        if state == CandidateAnalysisState.ANALYZED:
            state = CandidateAnalysisState.NOT_ANALYZED
        return CandidateAIFeedback(state=state)
    return CandidateAIFeedback(
        state=state,
        match_percentage=round(max(0.0, min(100.0, float(analysis.match_percentage)))),
        matched_skills=list(analysis.matched_skills),
        skills_to_improve=list(analysis.missing_skills),
        requirements_met=list(analysis.matched_requirements),
        requirements_to_strengthen=list(analysis.missing_requirements),
        analyzed_at=_aware(analysis.analyzed_at),
    )


def _safe_link(link: str | None) -> str | None:
    """Only http(s) links reach the candidate's browser.

    HR pastes meeting links as free text; anything else (``javascript:``,
    ``data:``, typos) would be unsafe or useless as a clickable link.
    """
    if not link:
        return None
    link = link.strip()
    return link if link.lower().startswith(("https://", "http://")) else None


def interview_view(interview: Interview) -> CandidateInterview:
    """An interview as the candidate sees it (no interviewer notes)."""
    job = interview.candidate.job
    upcoming = interview.status == InterviewStatus.UPCOMING
    link = _safe_link(interview.meeting_link)
    return CandidateInterview(
        id=interview.id,
        application_id=interview.candidate_id,
        position=job.position,
        company_name=job.company_name,
        scheduled_at=_aware(interview.scheduled_at),
        duration_minutes=interview.duration_minutes,
        status=interview.status.value,
        is_online=link is not None,
        meeting_link=link if upcoming else None,
        # TODO(CANDIDATE-INTERVIEW): a future phase can let candidates confirm,
        # decline or ask for another time. Add that as candidate-response
        # fields on Interview and expose them here; keep HR notes out.
    )


# ---------------------------------------------------------------------------
# Timeline
# ---------------------------------------------------------------------------


def _history_date(application: Application, predicate) -> datetime | None:
    """First recorded moment the application entered a status matching ``predicate``."""
    for entry in application.status_history or []:
        if predicate(entry.status):
            return _aware(entry.created_at)
    return None


def timeline(application: Application) -> list[TimelineStep]:
    """The five-step progress timeline, built only from stored facts.

    Dates come from the submission, the analysis, the interviews and the
    status history; a step whose real moment is unknown has ``date=None``.
    """
    status = application.application_status
    interviews = application.interviews or []
    upcoming, completed = _upcoming(interviews), _completed(interviews)
    final = status in _FINAL_STATUSES
    hr_started = status != ApplicationStatus.NEW or bool(interviews)

    submitted = TimelineStep(key="submitted", state=TimelineStepState.DONE, date=_aware(application.submitted_at))

    feedback_state = analysis_state(application)
    if feedback_state == CandidateAnalysisState.ANALYZED:
        analysis = stored_analysis(application)
        resume = TimelineStep(
            key="resume_review",
            state=TimelineStepState.DONE,
            date=_aware(analysis.analyzed_at) if analysis else None,
        )
    elif feedback_state == CandidateAnalysisState.ANALYZING:
        resume = TimelineStep(key="resume_review", state=TimelineStepState.CURRENT)
    elif feedback_state == CandidateAnalysisState.FAILED:
        # An AI problem is not an application problem: shown as unavailable.
        resume = TimelineStep(key="resume_review", state=TimelineStepState.UNAVAILABLE)
    elif hr_started or final:
        resume = TimelineStep(key="resume_review", state=TimelineStepState.SKIPPED)
    else:
        resume = TimelineStep(key="resume_review", state=TimelineStepState.UPCOMING)

    hr_review = TimelineStep(
        key="hr_review",
        state=TimelineStepState.DONE if hr_started or final else TimelineStepState.UPCOMING,
        date=_history_date(application, lambda s: s != ApplicationStatus.NEW.value),
    )

    if completed and not upcoming:
        interview = TimelineStep(
            key="interview", state=TimelineStepState.DONE, date=_aware(completed[-1].scheduled_at)
        )
    elif upcoming:
        interview = TimelineStep(
            key="interview", state=TimelineStepState.CURRENT, date=_aware(upcoming[0].scheduled_at)
        )
    elif status == ApplicationStatus.INTERVIEW:
        interview = TimelineStep(key="interview", state=TimelineStepState.CURRENT)
    elif final:
        interview = TimelineStep(key="interview", state=TimelineStepState.SKIPPED)
    else:
        interview = TimelineStep(key="interview", state=TimelineStepState.UPCOMING)

    if final:
        decision = TimelineStep(
            key="decision",
            state=TimelineStepState.DONE,
            date=_history_date(application, lambda s: s == status.value),
            outcome=_FINAL_OUTCOME[status],
        )
    else:
        decision = TimelineStep(key="decision", state=TimelineStepState.UPCOMING)

    steps = [submitted, resume, hr_review, interview, decision]
    # While the application is open, the first step still to come is "current".
    if not final and not any(step.state == TimelineStepState.CURRENT for step in steps):
        for step in steps:
            if step.state == TimelineStepState.UPCOMING:
                step.state = TimelineStepState.CURRENT
                break
    return steps


# ---------------------------------------------------------------------------
# Responses
# ---------------------------------------------------------------------------


def _interview_state(application: Application) -> CandidateInterviewState:
    interviews = application.interviews or []
    if _upcoming(interviews):
        return CandidateInterviewState.SCHEDULED
    if _completed(interviews):
        return CandidateInterviewState.COMPLETED
    return CandidateInterviewState.NOT_SCHEDULED


def application_summary(application: Application) -> CandidateApplicationSummary:
    upcoming = _upcoming(application.interviews or [])
    return CandidateApplicationSummary(
        id=application.id,
        position=application.job.position,
        company_name=application.job.company_name,
        submitted_at=_aware(application.submitted_at),
        status=candidate_status(application),
        analysis_state=analysis_state(application),
        interview_state=_interview_state(application),
        next_interview_at=_aware(upcoming[0].scheduled_at) if upcoming else None,
    )


def _answers(application: Application) -> list[CandidateAnswer]:
    """What the candidate submitted; file fields never expose a stored path."""
    response = application.application_response
    answers: list[CandidateAnswer] = []
    for item in (response.responses if response is not None else None) or []:
        if not isinstance(item, dict):
            continue
        field_type = str(item.get("type") or "")
        value = item.get("value")
        if field_type == "file":
            answers.append(
                CandidateAnswer(label=str(item.get("label") or ""), type=field_type, file_attached=bool(value))
            )
            continue
        if isinstance(value, list):
            clean: str | list[str] | None = [str(v) for v in value]
        elif value is None or value == "":
            clean = None
        else:
            clean = str(value)
        answers.append(CandidateAnswer(label=str(item.get("label") or ""), type=field_type, value=clean))
    return answers


def application_detail(application: Application) -> CandidateApplicationDetail:
    job = application.job
    interviews = sorted(application.interviews or [], key=lambda i: _aware(i.scheduled_at))
    return CandidateApplicationDetail(
        **application_summary(application).model_dump(),
        job=CandidateJob(
            position=job.position,
            company_name=job.company_name,
            description=job.description,
            required_skills=job.required_skills,
            required_experience=job.required_experience,
        ),
        has_resume=bool(application.resume_path),
        answers=_answers(application),
        analysis=ai_feedback(application),
        timeline=timeline(application),
        interviews=[interview_view(i) for i in interviews],
    )


def list_applications(db: Session, candidate: CandidateAccount) -> list[CandidateApplicationSummary]:
    return [application_summary(a) for a in application_crud.list_candidate_applications(db, candidate.id)]


def get_application(db: Session, candidate: CandidateAccount, application_id: int) -> Application | None:
    """The candidate's own application, or ``None`` (also for anyone else's)."""
    return application_crud.get_candidate_application(db, candidate.id, application_id)


def list_interviews(db: Session, candidate: CandidateAccount) -> list[CandidateInterview]:
    return [interview_view(i) for i in interview_crud.list_candidate_interviews(db, candidate.id)]


def get_interview(db: Session, candidate: CandidateAccount, interview_id: int) -> CandidateInterview | None:
    interview = interview_crud.get_candidate_interview(db, candidate.id, interview_id)
    return interview_view(interview) if interview is not None else None


def dashboard(db: Session, candidate: CandidateAccount) -> CandidateDashboard:
    """Counts and recent items for the candidate's dashboard (own data only)."""
    applications = application_crud.list_candidate_applications(db, candidate.id)
    upcoming = sorted(
        (i for a in applications for i in _upcoming(a.interviews or [])),
        key=lambda i: _aware(i.scheduled_at),
    )
    completed = sum(1 for a in applications if a.application_status in _FINAL_STATUSES)
    return CandidateDashboard(
        total_applications=len(applications),
        active_applications=len(applications) - completed,
        upcoming_interviews=len(upcoming),
        completed_applications=completed,
        next_interview=interview_view(upcoming[0]) if upcoming else None,
        recent_applications=[application_summary(a) for a in applications[:5]],
    )
