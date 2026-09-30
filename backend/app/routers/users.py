"""
Superuser-only endpoints to manage registered users.

All routes require an authenticated superuser (JWT + is_superuser=True),
otherwise a normal HR user receives 403 and an anonymous request 401.

These are the mutation endpoints the admin panel uses for activate /
deactivate / promote / demote / delete; the richer, paginated read views live
under ``/api/admin/users``. Safeguards and auditing are in
``app.services.user_admin``.
"""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.crud import user as user_crud
from app.dependencies.audit import get_audit_context
from app.dependencies.auth import get_current_superuser
from app.models.user import User
from app.schemas.user import AdminUserUpdate, UserResponse
from app.services import user_admin as user_admin_service
from app.services.audit import AuditContext

router = APIRouter()


def _get_user_or_404(db: Session, user_id: int) -> User:
    user = user_crud.get_user_by_id(db, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    return user


@router.get("", response_model=list[UserResponse])
def list_all_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_superuser),
) -> list[User]:
    """List all registered users (paginated). Superuser only."""
    return user_crud.list_users(db, skip=skip, limit=limit)


@router.get("/{user_id}", response_model=UserResponse)
def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_superuser),
) -> User:
    """Read a single registered user. Superuser only."""
    return _get_user_or_404(db, user_id)


@router.put("/{user_id}", response_model=UserResponse)
def update_user(
    user_id: int,
    payload: AdminUserUpdate,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_superuser),
    audit_ctx: AuditContext = Depends(get_audit_context),
) -> User:
    """Update a user's name / active / superuser flags. Superuser only.

    Errors:
    * 400 — the change would demote/deactivate the caller, or remove the last
      active administrator
    """
    target = _get_user_or_404(db, user_id)
    try:
        return user_admin_service.update_user(
            db, current_admin, target, payload.model_dump(exclude_unset=True), audit_ctx
        )
    except user_admin_service.UserAdminError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_superuser),
    audit_ctx: AuditContext = Depends(get_audit_context),
) -> None:
    """Delete a registered user and everything they own. Superuser only."""
    target = _get_user_or_404(db, user_id)
    try:
        user_admin_service.delete_user(db, current_admin, target, audit_ctx)
    except user_admin_service.UserAdminError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc