"""
Superuser-only endpoints to manage registered users.

All routes require an authenticated superuser (JWT + is_superuser=True),
otherwise a normal HR user receives 403 and an anonymous request 401.
"""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.crud import user as user_crud
from app.dependencies.auth import get_current_superuser
from app.models.user import User
from app.schemas.user import AdminUserUpdate, UserResponse

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
) -> User:
    """Update a user's name / active / superuser flags. Superuser only."""
    target = _get_user_or_404(db, user_id)
    data = payload.model_dump(exclude_unset=True)

    if target.id == current_admin.id and (
        data.get("is_superuser") is False or data.get("is_active") is False
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot demote or deactivate your own account",
        )

    update = {
        key: data[key]
        for key in ("full_name", "is_active", "is_superuser")
        if key in data
    }
    return user_crud.update_user(db, target, update)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_superuser),
) -> None:
    """Delete a registered user. Superuser only."""
    target = _get_user_or_404(db, user_id)
    if target.id == current_admin.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot delete your own account",
        )
    user_crud.delete_user(db, target)