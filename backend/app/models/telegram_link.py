"""SQLAlchemy models that bind a Telegram account to an HR user or a candidate.

How linking works
-----------------
1. A signed-in user asks the API for a link token (``TelegramLinkToken``).
   Only a SHA-256 digest of the token is stored; the raw token travels once,
   inside the ``https://t.me/<bot>?start=<token>`` deep link.
2. The user opens the link, Telegram sends ``/start <token>`` to the bot, and
   the bot consumes the token (single use, short-lived) and writes a
   ``TelegramLink`` row.

Accounts are never linked by phone number or username: those are not
verified, so matching on them would let anyone receive another person's
notifications.

``kind`` says which identity table the link points at. HR users and
candidates are separate identities (see ``models.candidate_account``), so one
Telegram account may hold one HR link and one candidate link at the same time.
"""

import enum
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class TelegramAccountKind(str, enum.Enum):
    """Which identity a Telegram link belongs to."""

    HR = "hr"
    CANDIDATE = "candidate"


_KIND_ENUM = Enum(
    TelegramAccountKind,
    name="telegram_account_kind",
    values_callable=lambda x: [e.value for e in x],
)

#: Exactly one owner column is set, and it matches ``kind``.
_ONE_OWNER = (
    "(kind = 'hr' AND user_id IS NOT NULL AND candidate_account_id IS NULL) OR "
    "(kind = 'candidate' AND candidate_account_id IS NOT NULL AND user_id IS NULL)"
)


class TelegramLink(Base):
    """A Telegram chat that receives notifications for one account."""

    __tablename__ = "telegram_links"
    __table_args__ = (
        CheckConstraint(_ONE_OWNER, name="ck_telegram_links_one_owner"),
        UniqueConstraint(
            "telegram_user_id", "kind", name="uq_telegram_links_telegram_user_kind"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[TelegramAccountKind] = mapped_column(_KIND_ENUM)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=True
    )
    candidate_account_id: Mapped[int | None] = mapped_column(
        ForeignKey("candidate_accounts.id", ondelete="CASCADE"), unique=True, nullable=True
    )
    telegram_user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    #: Private chat id the bot writes to (equal to the user id for private chats).
    chat_id: Mapped[int] = mapped_column(BigInteger)
    username: Mapped[str | None] = mapped_column(String(64), nullable=True)
    first_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    #: Telegram ``language_code`` reduced to one of the bot's languages.
    language: Mapped[str] = mapped_column(String(8), default="uz", server_default="uz")
    #: False once Telegram reports that the user blocked the bot.
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    linked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    last_seen_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Notification preferences, changed from the bot's /settings (phase 5).
    #: Candidate: status changes of their applications.
    notify_status: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    #: HR: new applications to their jobs.
    notify_new_applications: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true"
    )
    #: Both: reminders before an interview.
    notify_reminders: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")


class TelegramReminderWindow(str, enum.Enum):
    """How long before an interview a reminder goes out."""

    DAY = "24h"
    HOUR = "1h"


class TelegramInterviewReminder(Base):
    """One reminder window already handled for one interview time.

    The row is written before the messages are queued, so the periodic scan
    never sends the same reminder twice. ``scheduled_at`` is part of the key:
    moving an interview arms its reminders again.
    """

    __tablename__ = "telegram_interview_reminders"
    __table_args__ = (
        UniqueConstraint(
            "interview_id", "reminder_window", "scheduled_at", name="uq_telegram_interview_reminders"
        ),
        CheckConstraint(
            "reminder_window IN ('24h', '1h')", name="ck_telegram_interview_reminders_window"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    interview_id: Mapped[int] = mapped_column(
        ForeignKey("interviews.id", ondelete="CASCADE"), index=True
    )
    reminder_window: Mapped[str] = mapped_column(String(8))
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class TelegramLinkToken(Base):
    """A single-use token that proves who opened the bot's deep link."""

    __tablename__ = "telegram_link_tokens"
    __table_args__ = (
        CheckConstraint(_ONE_OWNER, name="ck_telegram_link_tokens_one_owner"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[TelegramAccountKind] = mapped_column(_KIND_ENUM)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=True
    )
    candidate_account_id: Mapped[int | None] = mapped_column(
        ForeignKey("candidate_accounts.id", ondelete="CASCADE"), index=True, nullable=True
    )
    #: SHA-256 hex digest of the raw token; the raw token is never stored.
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    #: Set when the token is consumed or superseded by a newer one.
    used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
