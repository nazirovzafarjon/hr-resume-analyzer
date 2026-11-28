"""Help Center support chat API.

Three routers share ``services.support``:

* ``hr_router``         ``/api/support/*``            HR users (verified email),
* ``candidate_router``  ``/api/candidate/support/*``  candidates (Candidate Portal tokens),
* ``admin_router``      ``/api/admin/support/*``      superusers in an admin session.

Each side also has a ``GET .../stream`` Server-Sent Events endpoint that pushes
"conversation changed" notices (see ``services.support_realtime``). The stream
authenticates once with its own short-lived database session and releases it
before streaming, so an open stream never holds a pooled connection.
EventSource cannot send an Authorization header, so the browser reads the
stream with ``fetch``; tokens never travel in the URL.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.database import SessionLocal, get_db
from app.core.errors import EmailVerificationRequiredError
from app.dependencies.audit import get_audit_context
from app.dependencies.auth import CurrentSession, get_current_session, get_current_superuser
from app.dependencies.candidate_auth import get_current_candidate
from app.models.candidate_account import CandidateAccount
from app.models.user import User
from app.schemas import support as schemas
from app.services import support as service
from app.services import support_realtime as realtime
from app.services.audit import AuditContext

_bearer_scheme = HTTPBearer(auto_error=False)


def _raise_http(exc: service.SupportError) -> None:
    raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


def get_hr_requester(session: CurrentSession = Depends(get_current_session)) -> service.Requester:
    """An HR user with a confirmed email (the HR panel's own rule)."""
    if not session.user.is_email_verified:
        raise EmailVerificationRequiredError()
    return service.Requester.hr(session.user)


def get_candidate_requester(
    candidate: CandidateAccount = Depends(get_current_candidate),
) -> service.Requester:
    return service.Requester.candidate(candidate)


def _authenticate_stream(resolve: Callable[[Session], list[str]]) -> list[str]:
    """Run an auth check on a private session that is closed before streaming."""
    db = SessionLocal()
    try:
        return resolve(db)
    finally:
        db.close()


def _stream(request: Request, channels: list[str]) -> StreamingResponse:
    return StreamingResponse(
        realtime.event_stream(request, channels),
        media_type="text/event-stream",
        headers=realtime.STREAM_HEADERS,
    )


# ---------------------------------------------------------------------------
# Requester routes (HR and candidate share the handlers)
# ---------------------------------------------------------------------------


def _requester_routes(router: APIRouter, requester_dep: Callable[..., service.Requester]) -> None:
    @router.get("/conversations", response_model=list[schemas.SupportConversationSummary])
    def list_conversations(
        requester: service.Requester = Depends(requester_dep), db: Session = Depends(get_db)
    ) -> list[dict]:
        return service.list_for_requester(db, requester)

    @router.get("/unread-count", response_model=schemas.SupportUnreadCount)
    def unread_count(
        requester: service.Requester = Depends(requester_dep), db: Session = Depends(get_db)
    ) -> dict:
        return {"unread_count": service.requester_unread_count(db, requester)}

    @router.post(
        "/conversations",
        response_model=schemas.SupportConversationDetail,
        status_code=status.HTTP_201_CREATED,
    )
    def open_conversation(
        payload: schemas.SupportConversationCreate,
        requester: service.Requester = Depends(requester_dep),
        db: Session = Depends(get_db),
    ) -> dict:
        try:
            return service.open_conversation(
                db, requester, body=payload.body, page_url=payload.page_url
            )
        except service.SupportError as exc:
            _raise_http(exc)

    @router.get("/conversations/{conversation_id}", response_model=schemas.SupportConversationDetail)
    def get_conversation(
        conversation_id: int,
        requester: service.Requester = Depends(requester_dep),
        db: Session = Depends(get_db),
    ) -> dict:
        try:
            return service.get_for_requester(db, requester, conversation_id)
        except service.SupportError as exc:
            _raise_http(exc)

    @router.post(
        "/conversations/{conversation_id}/messages",
        response_model=schemas.SupportConversationDetail,
        status_code=status.HTTP_201_CREATED,
    )
    def send_message(
        conversation_id: int,
        payload: schemas.SupportMessageCreate,
        requester: service.Requester = Depends(requester_dep),
        db: Session = Depends(get_db),
    ) -> dict:
        try:
            return service.add_requester_message(db, requester, conversation_id, body=payload.body)
        except service.SupportError as exc:
            _raise_http(exc)


hr_router = APIRouter()
_requester_routes(hr_router, get_hr_requester)

candidate_router = APIRouter()
_requester_routes(candidate_router, get_candidate_requester)


@hr_router.get("/stream", summary="Live support updates for the signed-in HR user (SSE)")
async def hr_stream(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> StreamingResponse:
    def resolve(db: Session) -> list[str]:
        session = get_current_session(db=db, credentials=credentials)
        return [get_hr_requester(session).channel]

    return _stream(request, await run_in_threadpool(_authenticate_stream, resolve))


@candidate_router.get("/stream", summary="Live support updates for the signed-in candidate (SSE)")
async def candidate_stream(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> StreamingResponse:
    def resolve(db: Session) -> list[str]:
        candidate = get_current_candidate(db=db, credentials=credentials)
        return [service.Requester.candidate(candidate).channel]

    return _stream(request, await run_in_threadpool(_authenticate_stream, resolve))


# ---------------------------------------------------------------------------
# Admin routes
# ---------------------------------------------------------------------------

admin_router = APIRouter(dependencies=[Depends(get_current_superuser)])
#: The stream checks the admin itself (see module docstring), so it lives on a
#: router without the request-scoped superuser dependency.
admin_stream_router = APIRouter()


@admin_router.get("/conversations", response_model=schemas.SupportAdminConversationPage)
def admin_list_conversations(
    status_filter: Literal["open", "closed"] | None = Query(None, alias="status"),
    kind: Literal["hr", "candidate"] | None = Query(None),
    q: str | None = Query(None, max_length=100),
    page: int = Query(1, ge=1, le=10_000),
    limit: int = Query(25, ge=1, le=100),
    db: Session = Depends(get_db),
) -> dict:
    items, total = service.admin_list(
        db,
        status=status_filter,
        kind=kind,
        q=(q.strip() or None) if q else None,
        page=page,
        limit=limit,
    )
    return {"items": items, "total": total, "page": page, "limit": limit}


@admin_router.get("/unread-count", response_model=schemas.SupportUnreadCount)
def admin_unread_count(db: Session = Depends(get_db)) -> dict:
    return {"unread_count": service.admin_unread_count(db)}


@admin_router.get(
    "/conversations/{conversation_id}", response_model=schemas.SupportAdminConversationDetail
)
def admin_get_conversation(conversation_id: int, db: Session = Depends(get_db)) -> dict:
    try:
        return service.admin_get(db, conversation_id)
    except service.SupportError as exc:
        _raise_http(exc)


@admin_router.post(
    "/conversations/{conversation_id}/messages",
    response_model=schemas.SupportAdminConversationDetail,
    status_code=status.HTTP_201_CREATED,
)
def admin_reply(
    conversation_id: int,
    payload: schemas.SupportMessageCreate,
    admin_user: User = Depends(get_current_superuser),
    db: Session = Depends(get_db),
) -> dict:
    try:
        return service.admin_reply(db, admin_user, conversation_id, body=payload.body)
    except service.SupportError as exc:
        _raise_http(exc)


@admin_router.post(
    "/conversations/{conversation_id}/close",
    response_model=schemas.SupportAdminConversationDetail,
)
def admin_close_conversation(
    conversation_id: int,
    admin_user: User = Depends(get_current_superuser),
    context: AuditContext = Depends(get_audit_context),
    db: Session = Depends(get_db),
) -> dict:
    try:
        return service.close_conversation(db, admin_user, conversation_id, context=context)
    except service.SupportError as exc:
        _raise_http(exc)


@admin_stream_router.get("/stream", summary="Live support updates for admins (SSE)")
async def admin_stream(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> StreamingResponse:
    def resolve(db: Session) -> list[str]:
        get_current_superuser(get_current_session(db=db, credentials=credentials))
        return [realtime.ADMIN_CHANNEL]

    return _stream(request, await run_in_threadpool(_authenticate_stream, resolve))
