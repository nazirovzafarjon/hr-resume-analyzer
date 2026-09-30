"""Administrative user management rules (activate, role changes, delete).

Shared by the existing ``/api/users`` endpoints so the safeguards live in one
place:

* An admin can never demote, deactivate or delete **their own** account, so
  nobody locks themselves out by accident.
* The **last active superuser** can never be demoted, deactivated or deleted
  by anyone, so the platform always keeps at least one administrator.

Deactivation takes effect immediately: ``get_current_user`` re-reads
``is_active`` on every request and refresh tokens are refused for inactive
accounts. Role changes are likewise read from the database per request.

Every change is audited with one row per effective change (e.g. a request
that both deactivates and demotes produces DEACTIVATE_USER and DEMOTE_USER).
"""

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

import logging

from app.core.security import hash_password
from app.crud import user as user_crud
from app.models.user import User
from app.schemas.user import UserCreate
from app.services import audit
from app.services.audit import AuditAction, AuditContext, AuditResource


logger = logging.getLogger(__name__)

#: Minimum length for a password taken from the environment.
MIN_CONFIGURED_PASSWORD_LENGTH = 8


class UserAdminError(Exception):
    """A requested change violates an admin safeguard (safe message)."""

    def __init__(self, message: str, status_code: int = 400) -> None:
        self.message = message
        self.status_code = status_code
        super().__init__(message)


SELF_DEMOTE_MESSAGE = "You cannot demote or deactivate your own account"
SELF_DELETE_MESSAGE = "You cannot delete your own account"
LAST_ADMIN_MESSAGE = "The platform must keep at least one active administrator"


def _active_superusers(db: Session) -> int:
    return db.execute(
        select(func.count(User.id)).where(User.is_superuser.is_(True), User.is_active.is_(True))
    ).scalar_one()


def _removes_admin_access(target: User, changes: dict[str, Any]) -> bool:
    """True when ``changes`` would take an active admin out of the admin pool."""
    if not (target.is_superuser and target.is_active):
        return False
    return changes.get("is_superuser") is False or changes.get("is_active") is False


def update_user(
    db: Session,
    admin: User,
    target: User,
    changes: dict[str, Any],
    context: AuditContext | None = None,
) -> User:
    """Apply name/active/role changes to ``target`` after the safeguards."""
    changes = {key: changes[key] for key in ("full_name", "is_active", "is_superuser") if key in changes}

    if target.id == admin.id and (
        changes.get("is_superuser") is False or changes.get("is_active") is False
    ):
        raise UserAdminError(SELF_DEMOTE_MESSAGE)
    if _removes_admin_access(target, changes) and _active_superusers(db) <= 1:
        raise UserAdminError(LAST_ADMIN_MESSAGE)

    before = {key: getattr(target, key) for key in changes}
    target = user_crud.update_user(db, target, changes)

    def log(action: str, details: dict[str, Any] | None = None) -> None:
        audit.record(
            db,
            action,
            resource_type=AuditResource.USER,
            resource_id=target.id,
            actor=admin,
            details={"target_email": target.email, **(details or {})},
            context=context,
        )

    if "is_active" in changes and changes["is_active"] != before["is_active"]:
        log(AuditAction.ACTIVATE_USER if changes["is_active"] else AuditAction.DEACTIVATE_USER)
    if "is_superuser" in changes and changes["is_superuser"] != before["is_superuser"]:
        log(AuditAction.PROMOTE_USER if changes["is_superuser"] else AuditAction.DEMOTE_USER)
    if "full_name" in changes and changes["full_name"] != before["full_name"]:
        log(AuditAction.UPDATE_USER, {"fields": ["full_name"]})
    return target


def delete_user(
    db: Session, admin: User, target: User, context: AuditContext | None = None
) -> None:
    """Delete ``target`` (their jobs, applications and interviews cascade)."""
    if target.id == admin.id:
        raise UserAdminError(SELF_DELETE_MESSAGE)
    if target.is_superuser and target.is_active and _active_superusers(db) <= 1:
        raise UserAdminError(LAST_ADMIN_MESSAGE)

    snapshot = {"target_email": target.email, "was_superuser": target.is_superuser}
    target_id = target.id
    user_crud.delete_user(db, target)
    audit.record(
        db,
        AuditAction.DELETE_USER,
        resource_type=AuditResource.USER,
        resource_id=target_id,
        actor=admin,
        details=snapshot,
        context=context,
    )


def ensure_configured_superuser(
    db: Session, *, email: str, password: str = "", full_name: str = "Administrator"
) -> User | None:
    """Make the account named by ``SUPERUSER_EMAIL`` an active administrator.

    Runs on every startup, so the configured person can always get into the
    admin console (e.g. after being demoted by mistake). Rules:

    * The account does not exist -> it is created as an active superuser,
      which requires ``SUPERUSER_PASSWORD`` (at least 8 characters).
    * The account exists -> it is promoted and reactivated if needed. Its
      password is set from ``SUPERUSER_PASSWORD`` **only if it has none yet**
      (e.g. a Google-only account): an existing password is never
      overwritten, so changing it in Settings keeps working across restarts.

    Other accounts are never touched, and every change is audited.
    """
    email = email.strip().lower()
    password = password or ""
    usable_password = len(password) >= MIN_CONFIGURED_PASSWORD_LENGTH
    if password and not usable_password:
        logger.error(
            "SUPERUSER_PASSWORD is shorter than %s characters and was ignored",
            MIN_CONFIGURED_PASSWORD_LENGTH,
        )

    user = user_crud.get_user_by_email(db, email)
    if user is None:
        if not usable_password:
            logger.error(
                "Superuser %s does not exist and SUPERUSER_PASSWORD is not set; not created",
                email,
            )
            return None
        user = user_crud.create_user(
            db, UserCreate(email=email, full_name=full_name or "Administrator", password=password),
            is_superuser=True,
        )
        logger.info("Created configured superuser %s", email)
        audit.record(
            db,
            AuditAction.REGISTER,
            resource_type=AuditResource.USER,
            resource_id=user.id,
            details={"method": "environment", "target_email": email, "superuser": True},
        )
        return user

    changes: dict = {}
    if not user.is_superuser:
        changes["is_superuser"] = True
    if not user.is_active:
        changes["is_active"] = True
    if user.hashed_password is None and usable_password:
        changes["hashed_password"] = hash_password(password)
    if not changes:
        return user

    user = user_crud.update_user(db, user, changes)
    logger.info("Configured superuser %s updated: %s", email, ", ".join(sorted(changes)))
    # Actor is None: the change comes from server configuration, not a person.
    if "is_superuser" in changes:
        audit.record(
            db,
            AuditAction.PROMOTE_USER,
            resource_type=AuditResource.USER,
            resource_id=user.id,
            details={"target_email": email, "source": "environment"},
        )
    if "is_active" in changes:
        audit.record(
            db,
            AuditAction.ACTIVATE_USER,
            resource_type=AuditResource.USER,
            resource_id=user.id,
            details={"target_email": email, "source": "environment"},
        )
    return user
