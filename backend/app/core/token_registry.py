"""Database-backed registry that invalidates already-issued JWTs.

Access and refresh tokens are stateless, so "log the user out of every device"
after a password change, "let a refresh token be used only once", logout and
workspace switching all need an extra signal. It is kept in two PostgreSQL
tables (see ``app.models.token_revocation``):

* ``session_cutoffs`` — one instant per user; every token whose ``iat``
  predates it was minted before the password changed and is rejected.
* ``revoked_tokens`` — denylist of individual ``jti`` ids (consumed refresh
  tokens, logged-out sessions, switched workspaces, used selection tokens).

Because the state lives in the database it survives API restarts and is shared
by every worker/instance, so a revoked token stays revoked everywhere. Token
``exp`` remains the hard bound: rows are pruned once the tokens they refer to
would have expired anyway.

Each function takes an optional ``db`` session. The request guard passes the
request's session so a revocation check costs one indexed lookup on an already
open connection; callers without one get a short-lived session of their own,
whose write is committed immediately (a revocation must never be rolled back
by an unrelated failure later in the request).
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import TypeVar

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.token_revocation import RevokedToken, SessionCutoff

#: Keep entries for longer than the longest token we issue (refresh tokens are
#: configured for 7 days by default); older rows can no longer matter.
_RETENTION = timedelta(days=30)

T = TypeVar("T")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@contextmanager
def _session(db: Session | None) -> Iterator[Session]:
    """Use the caller's session, or open (and close) a private one."""
    if db is not None:
        yield db
        return
    own = SessionLocal()
    try:
        yield own
    finally:
        own.close()


def _write(db: Session | None, work: Callable[[Session], T]) -> T:
    """Run a write and commit it (rolling back the caller's session on error)."""
    with _session(db) as session:
        try:
            result = work(session)
            session.commit()
            return result
        except Exception:
            session.rollback()
            raise


def revoke_sessions_before(
    user_id: int, when: datetime | None = None, db: Session | None = None
) -> datetime:
    """Reject every token for ``user_id`` issued before ``when``.

    The stored cutoff is rounded **up** to the next whole second because ``iat``
    is only second-granular: without the ceiling, a token minted in the same
    second as the password change would look older than it is and be wrongly
    revoked — or, with a floor, wrongly survive. Callers issue the replacement
    pair with the returned cutoff as its ``iat`` so it always passes.

    Args:
        user_id: The account whose existing sessions should stop working.
        when: Cutoff instant; defaults to now. Monotonic — calling this with an
            older timestamp never *un*-revokes already revoked tokens (the
            upsert keeps the later of the stored and the new cutoff, atomically,
            so concurrent requests cannot move it backwards either).

    Returns:
        The effective cutoff stored for the user.
    """
    moment = when or _utcnow()
    cutoff = (moment + timedelta(seconds=1)).replace(microsecond=0)

    def work(session: Session) -> datetime:
        stmt = insert(SessionCutoff).values(user_id=user_id, cutoff=cutoff)
        stmt = stmt.on_conflict_do_update(
            index_elements=[SessionCutoff.user_id],
            set_={"cutoff": func.greatest(SessionCutoff.cutoff, stmt.excluded.cutoff)},
        ).returning(SessionCutoff.cutoff)
        stored = session.execute(stmt).scalar_one()
        session.execute(delete(SessionCutoff).where(SessionCutoff.cutoff < _utcnow() - _RETENTION))
        return stored

    return _write(db, work)


def is_session_revoked(
    user_id: int, issued_at: datetime | None, db: Session | None = None
) -> bool:
    """Return ``True`` when a token predates the user's revocation cutoff.

    Tokens without an ``iat`` claim (issued before that claim existed) cannot be
    dated, so they are only rejected when the cutoff is still in the future —
    the conservative choice that never locks out sessions issued before an
    upgrade.
    """
    with _session(db) as session:
        cutoff = session.execute(
            select(SessionCutoff.cutoff).where(SessionCutoff.user_id == user_id)
        ).scalar_one_or_none()
    if cutoff is None:
        return False
    if issued_at is None:
        return cutoff > _utcnow()
    return issued_at < cutoff


def revoke_token(
    token_id: str | None, expires_at: datetime | None = None, db: Session | None = None
) -> None:
    """Deny-list a single token by its ``jti`` (refresh rotation, logout, ...)."""
    if not token_id:
        return
    expiry = expires_at or (_utcnow() + _RETENTION)

    def work(session: Session) -> None:
        session.execute(
            insert(RevokedToken)
            .values(jti=token_id[:64], expires_at=expiry)
            .on_conflict_do_nothing(index_elements=[RevokedToken.jti])
        )
        # Entries for tokens that have expired anyway can no longer matter.
        session.execute(delete(RevokedToken).where(RevokedToken.expires_at < _utcnow()))

    _write(db, work)


def is_token_revoked(token_id: str | None, db: Session | None = None) -> bool:
    """Return ``True`` when a specific ``jti`` has been consumed or revoked."""
    if not token_id:
        return False
    with _session(db) as session:
        return (
            session.execute(
                select(RevokedToken.jti).where(RevokedToken.jti == token_id[:64])
            ).first()
            is not None
        )


def reset_registry() -> None:
    """Drop all recorded state. Used by the test suite for isolation."""

    def work(session: Session) -> None:
        session.execute(delete(RevokedToken))
        session.execute(delete(SessionCutoff))

    _write(None, work)
