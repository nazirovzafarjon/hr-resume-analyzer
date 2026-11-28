"""Help Center support chat: rules shared by the requester and admin APIs.

Rules
-----
* A requester (HR user or candidate) has at most one **open** conversation.
  The Help button shows it; when an admin has closed it the requester starts
  a new one.
* A closed conversation is read-only for everybody.
* A requester only ever reaches their own conversations; an id belonging to
  someone else answers 404 (never 403), so ids cannot be probed.
* Every change is published to the live-update channels after it is saved
  (see ``services.support_realtime``).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.orm import Session

from app.core.rate_limit import SlidingWindowLimiter
from app.models.candidate_account import CandidateAccount
from app.models.support import (
    SupportConversation,
    SupportConversationStatus,
    SupportMessage,
    SupportRequesterKind,
    SupportSender,
)
from app.models.user import User
from app.services import audit
from app.services import support_realtime as realtime
from app.services.audit import AuditAction, AuditContext, AuditResource

PREVIEW_LENGTH = 160

#: Per requester: messages per minute, new conversations per hour.
_message_limiter = SlidingWindowLimiter(max_events=20, window_seconds=60)
_conversation_limiter = SlidingWindowLimiter(max_events=5, window_seconds=3600)


class SupportError(Exception):
    """A rule violation the API turns into an HTTP error."""

    status_code = 400

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


class ConversationNotFoundError(SupportError):
    status_code = 404

    def __init__(self) -> None:
        super().__init__("Conversation not found")


class ConversationClosedError(SupportError):
    status_code = 409

    def __init__(self) -> None:
        super().__init__("This conversation has been closed. Start a new one if you still need help.")


class OpenConversationExistsError(SupportError):
    status_code = 409

    def __init__(self) -> None:
        super().__init__("You already have an open conversation with support.")


class SupportRateLimitError(SupportError):
    status_code = 429

    def __init__(self) -> None:
        super().__init__("You are sending messages too quickly. Please wait a moment.")


def reset_rate_limits() -> None:
    """Forget recorded sends (used by the test suite)."""
    _message_limiter.reset()
    _conversation_limiter.reset()


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Requester identity
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Requester:
    """The HR user or candidate on the other side of a conversation."""

    kind: SupportRequesterKind
    id: int

    @classmethod
    def hr(cls, user: User) -> "Requester":
        return cls(SupportRequesterKind.HR, user.id)

    @classmethod
    def candidate(cls, account: CandidateAccount) -> "Requester":
        return cls(SupportRequesterKind.CANDIDATE, account.id)

    @property
    def key(self) -> str:
        return f"{self.kind.value}:{self.id}"

    @property
    def channel(self) -> str:
        return realtime.requester_channel(self.kind.value, self.id)

    def owns(self):
        """SQL condition: the conversation belongs to this requester."""
        column = (
            SupportConversation.user_id
            if self.kind is SupportRequesterKind.HR
            else SupportConversation.candidate_account_id
        )
        return and_(SupportConversation.requester_kind == self.kind.value, column == self.id)


def _requester_of(conversation: SupportConversation) -> Requester:
    kind = SupportRequesterKind(conversation.requester_kind)
    owner_id = (
        conversation.user_id if kind is SupportRequesterKind.HR else conversation.candidate_account_id
    )
    return Requester(kind, int(owner_id))


def _notify(event: str, conversation: SupportConversation, *, admins: bool = True, requester: bool = True) -> None:
    channels: list[str] = []
    if admins:
        channels.append(realtime.ADMIN_CHANNEL)
    if requester:
        channels.append(_requester_of(conversation).channel)
    realtime.publish(event, conversation.id, channels)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _add_message(
    db: Session,
    conversation: SupportConversation,
    *,
    sender: SupportSender,
    body: str,
    author: User | None = None,
) -> SupportMessage:
    now = _utcnow()
    message = SupportMessage(
        sender=sender.value,
        author_user_id=author.id if author is not None else None,
        author_name=(author.full_name or author.email) if author is not None else None,
        body=body,
        created_at=now,
    )
    conversation.messages.append(message)
    conversation.last_message_at = now
    db.flush()
    # The writer has obviously seen everything up to their own message.
    if sender is SupportSender.REQUESTER:
        conversation.requester_last_read_message_id = message.id
    else:
        conversation.admin_last_read_message_id = message.id
    return message


def _last_message_id(conversation: SupportConversation) -> int:
    return max((m.id for m in conversation.messages), default=0)


def _unread_for_requester(db: Session, conversation_ids: list[int]) -> dict[int, int]:
    if not conversation_ids:
        return {}
    rows = db.execute(
        select(SupportMessage.conversation_id, func.count(SupportMessage.id))
        .join(SupportConversation, SupportConversation.id == SupportMessage.conversation_id)
        .where(
            SupportMessage.conversation_id.in_(conversation_ids),
            SupportMessage.sender == SupportSender.ADMIN.value,
            SupportMessage.id > SupportConversation.requester_last_read_message_id,
        )
        .group_by(SupportMessage.conversation_id)
    ).all()
    return {conversation_id: count for conversation_id, count in rows}


def _summary(conversation: SupportConversation, unread: int) -> dict[str, Any]:
    return {
        "id": conversation.id,
        "status": conversation.status,
        "created_at": conversation.created_at,
        "last_message_at": conversation.last_message_at,
        "closed_at": conversation.closed_at,
        "unread_count": unread,
    }


# ---------------------------------------------------------------------------
# Requester side
# ---------------------------------------------------------------------------


def list_for_requester(db: Session, requester: Requester, *, limit: int = 20) -> list[dict[str, Any]]:
    """The requester's conversations, newest activity first."""
    conversations = (
        db.execute(
            select(SupportConversation)
            .where(requester.owns())
            .order_by(SupportConversation.last_message_at.desc(), SupportConversation.id.desc())
            .limit(limit)
        )
        .unique()
        .scalars()
        .all()
    )
    unread = _unread_for_requester(db, [c.id for c in conversations])
    return [_summary(c, unread.get(c.id, 0)) for c in conversations]


def requester_unread_count(db: Session, requester: Requester) -> int:
    return int(
        db.scalar(
            select(func.count(SupportMessage.id))
            .join(SupportConversation, SupportConversation.id == SupportMessage.conversation_id)
            .where(
                requester.owns(),
                SupportMessage.sender == SupportSender.ADMIN.value,
                SupportMessage.id > SupportConversation.requester_last_read_message_id,
            )
        )
        or 0
    )


def _get_owned(db: Session, requester: Requester, conversation_id: int) -> SupportConversation:
    conversation = (
        db.execute(
            select(SupportConversation).where(
                SupportConversation.id == conversation_id, requester.owns()
            )
        )
        .unique()
        .scalar_one_or_none()
    )
    if conversation is None:
        raise ConversationNotFoundError()
    return conversation


def _detail_for_requester(conversation: SupportConversation, unread: int) -> dict[str, Any]:
    return {**_summary(conversation, unread), "messages": list(conversation.messages)}


def get_for_requester(db: Session, requester: Requester, conversation_id: int) -> dict[str, Any]:
    """Open one conversation and mark the admins' replies in it as read."""
    conversation = _get_owned(db, requester, conversation_id)
    last_id = _last_message_id(conversation)
    if last_id > conversation.requester_last_read_message_id:
        conversation.requester_last_read_message_id = last_id
        db.commit()
        db.refresh(conversation)
        # Other tabs of the same requester drop their unread badge.
        _notify("read", conversation, admins=False)
    return _detail_for_requester(conversation, 0)


def open_conversation(
    db: Session, requester: Requester, *, body: str, page_url: str | None
) -> dict[str, Any]:
    """Start a conversation with its first message."""
    existing = db.scalar(
        select(SupportConversation.id).where(
            requester.owns(), SupportConversation.status == SupportConversationStatus.OPEN.value
        )
    )
    if existing is not None:
        raise OpenConversationExistsError()
    if not _conversation_limiter.check(requester.key):
        raise SupportRateLimitError()
    _message_limiter.check(requester.key)

    now = _utcnow()
    conversation = SupportConversation(
        requester_kind=requester.kind.value,
        user_id=requester.id if requester.kind is SupportRequesterKind.HR else None,
        candidate_account_id=requester.id if requester.kind is SupportRequesterKind.CANDIDATE else None,
        status=SupportConversationStatus.OPEN.value,
        page_url=page_url or None,
        created_at=now,
        last_message_at=now,
    )
    db.add(conversation)
    db.flush()
    _add_message(db, conversation, sender=SupportSender.REQUESTER, body=body)
    db.commit()
    db.refresh(conversation)
    _notify("conversation", conversation)
    return _detail_for_requester(conversation, 0)


def add_requester_message(
    db: Session, requester: Requester, conversation_id: int, *, body: str
) -> dict[str, Any]:
    conversation = _get_owned(db, requester, conversation_id)
    if not conversation.is_open:
        raise ConversationClosedError()
    if not _message_limiter.check(requester.key):
        raise SupportRateLimitError()
    # Replying means the requester has read everything so far.
    conversation.requester_last_read_message_id = _last_message_id(conversation)
    _add_message(db, conversation, sender=SupportSender.REQUESTER, body=body)
    db.commit()
    db.refresh(conversation)
    _notify("message", conversation)
    return _detail_for_requester(conversation, 0)


# ---------------------------------------------------------------------------
# Admin side
# ---------------------------------------------------------------------------

_ADMIN_UNREAD = case(
    (
        and_(
            SupportMessage.sender == SupportSender.REQUESTER.value,
            SupportMessage.id > SupportConversation.admin_last_read_message_id,
        ),
        1,
    ),
)


def admin_unread_count(db: Session) -> int:
    """How many conversations have requester messages no admin has read."""
    return int(
        db.scalar(
            select(func.count(func.distinct(SupportMessage.conversation_id)))
            .join(SupportConversation, SupportConversation.id == SupportMessage.conversation_id)
            .where(
                SupportMessage.sender == SupportSender.REQUESTER.value,
                SupportMessage.id > SupportConversation.admin_last_read_message_id,
            )
        )
        or 0
    )


def _admin_rows(db: Session, conversations: list[SupportConversation]) -> list[dict[str, Any]]:
    ids = [c.id for c in conversations]
    if not ids:
        return []
    stats = {
        conversation_id: (count, unread, last_id)
        for conversation_id, count, unread, last_id in db.execute(
            select(
                SupportMessage.conversation_id,
                func.count(SupportMessage.id),
                func.count(_ADMIN_UNREAD),
                func.max(SupportMessage.id),
            )
            .join(SupportConversation, SupportConversation.id == SupportMessage.conversation_id)
            .where(SupportMessage.conversation_id.in_(ids))
            .group_by(SupportMessage.conversation_id)
        ).all()
    }
    last_ids = [s[2] for s in stats.values()]
    previews = dict(
        db.execute(
            select(SupportMessage.conversation_id, SupportMessage.body).where(
                SupportMessage.id.in_(last_ids)
            )
        ).all()
    ) if last_ids else {}

    rows = []
    for c in conversations:
        count, unread, _ = stats.get(c.id, (0, 0, 0))
        preview = " ".join((previews.get(c.id) or "").split())
        if len(preview) > PREVIEW_LENGTH:
            preview = preview[: PREVIEW_LENGTH - 1].rstrip() + "…"
        rows.append(
            {
                "id": c.id,
                "status": c.status,
                "requester_kind": c.requester_kind,
                "requester_name": c.requester_name,
                "requester_email": c.requester_email,
                "preview": preview,
                "message_count": count,
                "unread_count": unread,
                "created_at": c.created_at,
                "last_message_at": c.last_message_at,
                "closed_at": c.closed_at,
            }
        )
    return rows


def admin_list(
    db: Session,
    *,
    status: str | None,
    kind: str | None,
    q: str | None,
    page: int,
    limit: int,
) -> tuple[list[dict[str, Any]], int]:
    """Inbox listing, newest activity first."""
    query = (
        select(SupportConversation)
        .outerjoin(User, User.id == SupportConversation.user_id)
        .outerjoin(CandidateAccount, CandidateAccount.id == SupportConversation.candidate_account_id)
    )
    if status:
        query = query.where(SupportConversation.status == status)
    if kind:
        query = query.where(SupportConversation.requester_kind == kind)
    if q:
        pattern = f"%{q}%"
        body_match = (
            select(SupportMessage.id)
            .where(
                SupportMessage.conversation_id == SupportConversation.id,
                SupportMessage.body.ilike(pattern),
            )
            .exists()
        )
        query = query.where(
            or_(
                User.full_name.ilike(pattern),
                User.email.ilike(pattern),
                CandidateAccount.full_name.ilike(pattern),
                CandidateAccount.email.ilike(pattern),
                body_match,
            )
        )

    total = int(db.scalar(select(func.count()).select_from(query.subquery())) or 0)
    conversations = (
        db.execute(
            query.order_by(SupportConversation.last_message_at.desc(), SupportConversation.id.desc())
            .offset((page - 1) * limit)
            .limit(limit)
        )
        .unique()
        .scalars()
        .all()
    )
    return _admin_rows(db, list(conversations)), total


def _get_any(db: Session, conversation_id: int) -> SupportConversation:
    conversation = db.get(SupportConversation, conversation_id)
    if conversation is None:
        raise ConversationNotFoundError()
    return conversation


def _admin_detail(db: Session, conversation: SupportConversation) -> dict[str, Any]:
    row = _admin_rows(db, [conversation])[0]
    closed_by = db.get(User, conversation.closed_by_id) if conversation.closed_by_id else None
    return {
        **row,
        "page_url": conversation.page_url,
        "closed_by_name": (closed_by.full_name or closed_by.email) if closed_by else None,
        "requester_id": conversation.user_id or conversation.candidate_account_id,
        "messages": list(conversation.messages),
    }


def admin_get(db: Session, conversation_id: int) -> dict[str, Any]:
    """Open a conversation in the inbox and mark it read for the admins."""
    conversation = _get_any(db, conversation_id)
    last_id = _last_message_id(conversation)
    if last_id > conversation.admin_last_read_message_id:
        conversation.admin_last_read_message_id = last_id
        db.commit()
        db.refresh(conversation)
        _notify("read", conversation, requester=False)
    return _admin_detail(db, conversation)


def admin_reply(db: Session, admin_user: User, conversation_id: int, *, body: str) -> dict[str, Any]:
    conversation = _get_any(db, conversation_id)
    if not conversation.is_open:
        raise ConversationClosedError()
    _add_message(db, conversation, sender=SupportSender.ADMIN, body=body, author=admin_user)
    db.commit()
    db.refresh(conversation)
    _notify("message", conversation)
    return _admin_detail(db, conversation)


def close_conversation(
    db: Session, admin_user: User, conversation_id: int, *, context: AuditContext | None = None
) -> dict[str, Any]:
    """Close a conversation for good. Closing twice is a no-op."""
    conversation = _get_any(db, conversation_id)
    if conversation.is_open:
        conversation.status = SupportConversationStatus.CLOSED.value
        conversation.closed_at = _utcnow()
        conversation.closed_by_id = admin_user.id
        conversation.admin_last_read_message_id = _last_message_id(conversation)
        db.commit()
        audit.record(
            db,
            AuditAction.SUPPORT_CLOSED,
            resource_type=AuditResource.SUPPORT,
            resource_id=conversation.id,
            actor=admin_user,
            details={"requester_kind": conversation.requester_kind},
            context=context,
        )
        db.refresh(conversation)
        _notify("closed", conversation)
    return _admin_detail(db, conversation)
