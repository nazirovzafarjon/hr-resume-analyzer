"""Link and unlink Telegram accounts (see ``models.telegram_link`` for the flow).

Both the API (issuing tokens, showing and removing a link) and the bot
process (consuming a token from ``/start <token>``) go through this module, so
every rule lives in one place:

* tokens are random, single use, short-lived and stored only as a digest;
* issuing a new token supersedes the account's older unused tokens;
* only an active account with a verified email can be linked;
* one account has at most one Telegram chat, and one Telegram account has at
  most one link per kind (re-linking moves the link instead of failing).
"""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.config import settings
from app.crud import candidate_account as candidate_crud
from app.crud import user as user_crud
from app.models.candidate_account import CandidateAccount
from app.models.telegram_link import TelegramAccountKind, TelegramLink, TelegramLinkToken
from app.models.user import User
from app.services import audit
from app.services.audit import AuditAction, AuditContext, AuditResource

#: Languages the bot speaks; anything else falls back to Uzbek.
SUPPORTED_LANGUAGES = ("uz", "ru", "en")

Owner = User | CandidateAccount


class TelegramNotConfiguredError(RuntimeError):
    """The bot is switched off or has no token/username configured."""


class LinkTokenError(Exception):
    """A ``/start`` token could not be used. ``code`` picks the bot's reply."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class IssuedLinkToken:
    deep_link: str
    expires_at: datetime


@dataclass(frozen=True)
class TelegramProfile:
    """What the bot knows about the Telegram user who sent ``/start``."""

    telegram_user_id: int
    chat_id: int
    username: str | None = None
    first_name: str | None = None
    language_code: str | None = None


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def normalize_language(language_code: str | None) -> str:
    """Reduce Telegram's ``language_code`` (e.g. ``ru-RU``) to a bot language."""
    code = (language_code or "").split("-")[0].lower()
    return code if code in SUPPORTED_LANGUAGES else "uz"


def _owner_kind(owner: Owner) -> TelegramAccountKind:
    return TelegramAccountKind.HR if isinstance(owner, User) else TelegramAccountKind.CANDIDATE


def _owner_filter(model, owner: Owner):
    if isinstance(owner, User):
        return model.user_id == owner.id
    return model.candidate_account_id == owner.id


def _owner_columns(owner: Owner) -> dict[str, int | None]:
    if isinstance(owner, User):
        return {"user_id": owner.id, "candidate_account_id": None}
    return {"user_id": None, "candidate_account_id": owner.id}


def _owner_can_link(owner: Owner | None) -> bool:
    return owner is not None and owner.is_active and owner.is_email_verified


def _audit(db: Session, owner: Owner, action: str, link: TelegramLink | None) -> None:
    audit.record(
        db,
        action,
        resource_type=AuditResource.TELEGRAM,
        resource_id=link.id if link is not None else None,
        actor=owner if isinstance(owner, User) else None,
        details={
            "kind": _owner_kind(owner).value,
            "candidate_account_id": owner.id if isinstance(owner, CandidateAccount) else None,
        },
        context=AuditContext(),
    )


# ---------------------------------------------------------------------------
# API side
# ---------------------------------------------------------------------------


def get_link(db: Session, owner: Owner) -> TelegramLink | None:
    return db.query(TelegramLink).filter(_owner_filter(TelegramLink, owner)).one_or_none()


def issue_link_token(db: Session, owner: Owner) -> IssuedLinkToken:
    """Create a fresh deep link for ``owner`` and supersede older tokens."""
    if not settings.telegram_configured:
        raise TelegramNotConfiguredError
    now = _utcnow()
    db.query(TelegramLinkToken).filter(
        _owner_filter(TelegramLinkToken, owner), TelegramLinkToken.used_at.is_(None)
    ).update({TelegramLinkToken.used_at: now}, synchronize_session=False)

    raw_token = secrets.token_urlsafe(24)  # 32 chars of [A-Za-z0-9_-], within /start's 64
    expires_at = now + timedelta(minutes=settings.TELEGRAM_LINK_TOKEN_EXPIRE_MINUTES)
    db.add(
        TelegramLinkToken(
            kind=_owner_kind(owner),
            token_hash=hash_token(raw_token),
            expires_at=expires_at,
            **_owner_columns(owner),
        )
    )
    db.commit()
    return IssuedLinkToken(
        deep_link=f"https://t.me/{settings.TELEGRAM_BOT_USERNAME}?start={raw_token}",
        expires_at=expires_at,
    )


def unlink(db: Session, owner: Owner) -> bool:
    """Remove ``owner``'s link. Returns False when there was none."""
    link = get_link(db, owner)
    if link is None:
        return False
    db.delete(link)
    db.commit()
    _audit(db, owner, AuditAction.TELEGRAM_UNLINKED, None)
    return True


# ---------------------------------------------------------------------------
# Bot side
# ---------------------------------------------------------------------------


def _resolve_owner(db: Session, token: TelegramLinkToken) -> Owner | None:
    if token.kind == TelegramAccountKind.HR:
        return user_crud.get_user_by_id(db, token.user_id)
    return candidate_crud.get_by_id(db, token.candidate_account_id)


def consume_link_token(db: Session, raw_token: str, profile: TelegramProfile) -> TelegramLink:
    """Link the Telegram user behind ``profile`` to the token's account.

    Raises ``LinkTokenError`` with code ``invalid`` (unknown or already used),
    ``expired`` or ``inactive`` (account deactivated or email unverified).
    """
    token = (
        db.query(TelegramLinkToken)
        .filter(TelegramLinkToken.token_hash == hash_token(raw_token))
        .with_for_update()
        .one_or_none()
    )
    if token is None or token.used_at is not None:
        db.rollback()
        raise LinkTokenError("invalid")
    now = _utcnow()
    if token.expires_at <= now:
        db.rollback()
        raise LinkTokenError("expired")
    owner = _resolve_owner(db, token)
    if not _owner_can_link(owner):
        db.rollback()
        raise LinkTokenError("inactive")

    token.used_at = now
    # Re-linking replaces: drop this account's old chat and any other account
    # of the same kind that this Telegram user was linked to before.
    db.query(TelegramLink).filter(
        or_(
            _owner_filter(TelegramLink, owner),
            (TelegramLink.telegram_user_id == profile.telegram_user_id)
            & (TelegramLink.kind == token.kind),
        )
    ).delete(synchronize_session=False)
    link = TelegramLink(
        kind=token.kind,
        telegram_user_id=profile.telegram_user_id,
        chat_id=profile.chat_id,
        username=profile.username[:64] if profile.username else None,
        first_name=profile.first_name[:255] if profile.first_name else None,
        language=normalize_language(profile.language_code),
        is_active=True,
        last_seen_at=now,
        **_owner_columns(owner),
    )
    db.add(link)
    db.commit()
    db.refresh(link)
    _audit(db, owner, AuditAction.TELEGRAM_LINKED, link)
    return link


def links_for_telegram_user(db: Session, telegram_user_id: int) -> list[TelegramLink]:
    """Links of one Telegram user whose accounts are still allowed to use the bot."""
    links = (
        db.query(TelegramLink)
        .filter(TelegramLink.telegram_user_id == telegram_user_id)
        .order_by(TelegramLink.kind)
        .all()
    )
    usable = []
    for link in links:
        owner = owner_of(db, link)
        if _owner_can_link(owner):
            usable.append(link)
    return usable


def owner_of(db: Session, link: TelegramLink) -> Owner | None:
    if link.kind == TelegramAccountKind.HR:
        return user_crud.get_user_by_id(db, link.user_id)
    return candidate_crud.get_by_id(db, link.candidate_account_id)


def touch(db: Session, telegram_user_id: int, chat_id: int) -> None:
    """Record activity and re-enable a chat that had blocked and unblocked the bot."""
    db.query(TelegramLink).filter(TelegramLink.telegram_user_id == telegram_user_id).update(
        {
            TelegramLink.last_seen_at: _utcnow(),
            TelegramLink.chat_id: chat_id,
            TelegramLink.is_active: True,
        },
        synchronize_session=False,
    )
    db.commit()


def unlink_telegram_user(db: Session, telegram_user_id: int) -> int:
    """Remove every link of a Telegram user (the bot's ``/unlink``). Returns the count."""
    links = db.query(TelegramLink).filter(TelegramLink.telegram_user_id == telegram_user_id).all()
    owners = [owner_of(db, link) for link in links]
    for link in links:
        db.delete(link)
    db.commit()
    for owner in owners:
        if owner is not None:
            _audit(db, owner, AuditAction.TELEGRAM_UNLINKED, None)
    return len(links)
