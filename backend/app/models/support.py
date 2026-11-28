"""SQLAlchemy models for the Help Center: support chats between users and admins.

An HR user or a candidate opens a conversation from the floating "Help"
button in their portal; every admin sees it in the admin console's Support
inbox and can reply. Once an admin closes it the conversation is read-only:
the requester starts a new one for a new problem.

``requester_kind`` says which identity table the requester lives in. HR users
and candidates are separate identities (see ``models.candidate_account``), so a
conversation points at exactly one of ``user_id`` / ``candidate_account_id``.

Unread state is kept per side as the id of the last message that side has
seen (ids only grow, so there are no clock or same-transaction ties): a
message is unread for the admins when its id is above
``admin_last_read_message_id`` and the requester wrote it, and unread for the
requester when its id is above ``requester_last_read_message_id`` and an admin
wrote it.
"""

from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class SupportRequesterKind(str, enum.Enum):
    """Which identity opened a support conversation."""

    HR = "hr"
    CANDIDATE = "candidate"


class SupportConversationStatus(str, enum.Enum):
    """Lifecycle of a support conversation."""

    OPEN = "open"
    CLOSED = "closed"


class SupportSender(str, enum.Enum):
    """Who wrote a support message."""

    REQUESTER = "requester"
    ADMIN = "admin"


_ONE_REQUESTER = (
    "(requester_kind = 'hr' AND user_id IS NOT NULL AND candidate_account_id IS NULL) OR "
    "(requester_kind = 'candidate' AND candidate_account_id IS NOT NULL AND user_id IS NULL)"
)


class SupportConversation(Base):
    """One support thread opened by an HR user or a candidate."""

    __tablename__ = "support_conversations"
    __table_args__ = (
        CheckConstraint(_ONE_REQUESTER, name="ck_support_conversations_one_requester"),
        CheckConstraint(
            "requester_kind IN ('hr', 'candidate')", name="ck_support_conversations_kind"
        ),
        CheckConstraint("status IN ('open', 'closed')", name="ck_support_conversations_status"),
        Index("ix_support_conversations_status_last", "status", "last_message_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    requester_kind: Mapped[str] = mapped_column(String(16))
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True
    )
    candidate_account_id: Mapped[int | None] = mapped_column(
        ForeignKey("candidate_accounts.id", ondelete="CASCADE"), nullable=True, index=True
    )
    status: Mapped[str] = mapped_column(
        String(16), default=SupportConversationStatus.OPEN.value, server_default="open"
    )
    #: The portal page the requester was on when they opened the chat.
    page_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    last_message_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    admin_last_read_message_id: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0"
    )
    requester_last_read_message_id: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0"
    )
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    user = relationship("User", foreign_keys=[user_id], lazy="joined")
    candidate_account = relationship("CandidateAccount", lazy="joined")
    messages: Mapped[list["SupportMessage"]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="SupportMessage.id",
        passive_deletes=True,
    )

    @property
    def is_open(self) -> bool:
        return self.status == SupportConversationStatus.OPEN.value

    @property
    def requester_name(self) -> str:
        person = self.user if self.requester_kind == SupportRequesterKind.HR.value else self.candidate_account
        if person is None:
            return ""
        return (person.full_name or "").strip() or person.email

    @property
    def requester_email(self) -> str:
        person = self.user if self.requester_kind == SupportRequesterKind.HR.value else self.candidate_account
        return person.email if person is not None else ""


class SupportMessage(Base):
    """One message inside a support conversation."""

    __tablename__ = "support_messages"
    __table_args__ = (
        CheckConstraint("sender IN ('requester', 'admin')", name="ck_support_messages_sender"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    conversation_id: Mapped[int] = mapped_column(
        ForeignKey("support_conversations.id", ondelete="CASCADE"), index=True
    )
    sender: Mapped[str] = mapped_column(String(16))
    #: The admin who wrote an ``admin`` message (kept as a name if they are deleted).
    author_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    author_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    conversation: Mapped[SupportConversation] = relationship(back_populates="messages")
