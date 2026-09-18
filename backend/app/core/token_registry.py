"""In-process registry that invalidates already-issued JWTs.

Access and refresh tokens are stateless, so "log the user out of every device"
after a password change, and "let a refresh token be used only once", both need
an extra signal. Rather than adding columns to ``users`` (and a migration), the
registry keeps two small pieces of bookkeeping:

* **cutoff** per user — every token whose ``iat`` predates it was minted before
  the password changed and is therefore rejected.
* **denylist** of ``jti`` ids — individual tokens consumed (rotated) or revoked.

Scope and limitations (deliberate MVP trade-off):
* The state lives in the worker's memory. Restarting the API, or running several
  uvicorn workers behind a load balancer, narrows these guarantees; token ``exp``
  stays the hard bound in every case.
* For a multi-instance deployment, back this module with a shared store (e.g.
  Redis keys with a TTL equal to the refresh-token lifetime, or a
  ``users.token_version`` column). Only these four functions are used elsewhere,
  so nothing else needs to change.
"""

from __future__ import annotations

import threading
from datetime import datetime, timedelta, timezone

#: Keep entries for longer than the longest token we issue (refresh tokens are
#: configured for 7 days by default), then prune so memory cannot grow unbounded.
_RETENTION = timedelta(days=30)

_lock = threading.Lock()
# user id -> tokens issued strictly before this instant are no longer trusted.
_cutoffs: dict[int, datetime] = {}
# consumed/revoked token ids -> expiry used for pruning.
_revoked: dict[str, datetime] = {}


def revoke_sessions_before(user_id: int, when: datetime | None = None) -> datetime:
    """Reject every token for ``user_id`` issued before ``when``.

    The stored cutoff is rounded **up** to the next whole second because ``iat``
    is only second-granular: without the ceiling, a token minted in the same
    second as the password change would look older than it is and be wrongly
    revoked — or, with a floor, wrongly survive. Callers issue the replacement
    pair with the returned cutoff as its ``iat`` so it always passes.

    Args:
        user_id: The account whose existing sessions should stop working.
        when: Cutoff instant; defaults to now. Monotonic — calling this with an
            older timestamp never *un*-revokes already revoked tokens.

    Returns:
        The effective cutoff stored for the user.
    """
    moment = when or datetime.now(timezone.utc)
    cutoff = (moment + timedelta(seconds=1)).replace(microsecond=0)
    with _lock:
        current = _cutoffs.get(user_id)
        if current is not None and current >= cutoff:
            return current
        _cutoffs[user_id] = cutoff
        _prune_locked()
        return cutoff


def is_session_revoked(user_id: int, issued_at: datetime | None) -> bool:
    """Return ``True`` when a token predates the user's revocation cutoff.

    Tokens without an ``iat`` claim (issued before that claim existed) cannot be
    dated, so they are only rejected when the cutoff is still in the future —
    the conservative choice that never locks out sessions issued before an
    upgrade.
    """
    with _lock:
        cutoff = _cutoffs.get(user_id)
        if cutoff is None:
            return False
    if issued_at is None:
        return cutoff > datetime.now(timezone.utc)
    return issued_at < cutoff


def revoke_token(token_id: str, expires_at: datetime | None = None) -> None:
    """Deny-list a single token by its ``jti`` (used for refresh rotation)."""
    if not token_id:
        return
    with _lock:
        _revoked[token_id] = expires_at or (datetime.now(timezone.utc) + _RETENTION)
        _prune_locked()


def is_token_revoked(token_id: str | None) -> bool:
    """Return ``True`` when a specific ``jti`` has been consumed or revoked."""
    if not token_id:
        return False
    with _lock:
        return token_id in _revoked


def reset_registry() -> None:
    """Drop all recorded state. Used by the test suite for isolation."""
    with _lock:
        _cutoffs.clear()
        _revoked.clear()


def _prune_locked() -> None:
    """Remove entries past the retention window (caller must hold the lock)."""
    if len(_cutoffs) < 128 and len(_revoked) < 128:
        return  # never worth pruning a nearly-empty registry
    floor = datetime.now(timezone.utc) - _RETENTION
    for user_id, cutoff in list(_cutoffs.items()):
        if cutoff < floor:
            del _cutoffs[user_id]
    for token_id, expires_at in list(_revoked.items()):
        if expires_at < datetime.now(timezone.utc):
            del _revoked[token_id]
        elif expires_at < floor:
            del _revoked[token_id]