"""Session roles ("workspaces") and which of them an account may use.

The account model stays unchanged: ``User.is_superuser`` is still the source
of truth for admin *capability*. What this module adds is the *active* role of
one session, chosen at sign-in and signed into the JWT by the server:

* ``user``  — the HR workspace. Every account has it.
* ``admin`` — the admin console. Only accounts with ``is_superuser``.

An account with a single role enters that workspace directly; an account with
both must pick one explicitly at sign-in (see ``services.auth``). Admin
endpoints require **both** the capability and an admin session, so a
superuser working in the HR workspace cannot call them until they switch.
"""

import enum
from typing import Any

from app.models.user import User

#: JWT claim that carries the session role (set only by the server).
ROLE_CLAIM = "role"


class SessionRole(str, enum.Enum):
    USER = "user"
    ADMIN = "admin"


def available_roles(user: User) -> list[SessionRole]:
    """Roles this account may use, HR first (the default workspace)."""
    roles = [SessionRole.USER]
    if user.is_superuser:
        roles.append(SessionRole.ADMIN)
    return roles


def token_role(payload: dict[str, Any]) -> SessionRole:
    """The session role signed into a decoded token.

    Tokens issued before roles existed carry no claim and are treated as the
    HR workspace: the least-privileged choice, so an old admin session has to
    sign in again (and choose) before it can reach admin endpoints.
    """
    return SessionRole.ADMIN if payload.get(ROLE_CLAIM) == SessionRole.ADMIN.value else SessionRole.USER
