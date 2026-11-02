"""Admin notifications router (``/api/admin/notifications``). Superuser only.

Provides management endpoints for public Contact Us messages/inquiries surfaced
to administrators as notifications in the CRM:
- List paginated notifications with optional read status and search
- Get unread inquiries count
- Mark inquiry as read / unread
- Delete inquiry
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.crud import contact_message as contact_crud
from app.dependencies.auth import get_current_superuser
from app.models.user import User
from app.schemas import admin as schemas
from app.schemas.contact_message import (
    ContactMessageAdminRow,
    ContactMessagePage,
    ContactMessageUpdateRead,
    ContactUnreadCount,
)

router = APIRouter(dependencies=[Depends(get_current_superuser)])
notifications_admin_router = router

ADMIN_ONLY = "Superuser only: 401 without a token, 403 for non-admin users."

PageParam = Query(1, ge=1, le=10_000, description="Page number, starting at 1")
LimitParam = Query(25, ge=1, le=schemas.MAX_PAGE_SIZE, description="Rows per page (max 100)")
SearchParam = Query(None, max_length=100, description="Case-insensitive search")


def _clean(search: str | None) -> str | None:
    """Treat a blank search box like no search."""
    return (search.strip() or None) if search else None


@router.get(
    "",
    response_model=ContactMessagePage,
    summary="List contact inquiries",
    description=f"{ADMIN_ONLY} Paginated and sorted by created_at DESC with optional read status and search filter.",
)
@router.get(
    "/",
    response_model=ContactMessagePage,
    include_in_schema=False,
)
def list_notifications(
    page: int = PageParam,
    limit: int = LimitParam,
    is_read: bool | None = Query(None, description="Filter by read status (true, false, or omitted for all)"),
    q: str | None = SearchParam,
    db: Session = Depends(get_db),
    _current_admin: User = Depends(get_current_superuser),
) -> dict:
    items, total, unread_count = contact_crud.get_contact_messages(
        db, page=page, limit=limit, is_read=is_read, q=_clean(q)
    )
    return {
        "items": items,
        "total": total,
        "unread_count": unread_count,
        "page": page,
        "limit": limit,
    }


# IMPORTANT: /unread-count MUST be defined before /{id} to avoid path shadowing
@router.get(
    "/unread-count",
    response_model=ContactUnreadCount,
    summary="Get unread contact inquiries count",
    description=ADMIN_ONLY,
)
@router.get(
    "/unread-count/",
    response_model=ContactUnreadCount,
    include_in_schema=False,
)
def get_notifications_unread_count(
    db: Session = Depends(get_db),
    _current_admin: User = Depends(get_current_superuser),
) -> dict:
    return {"unread_count": contact_crud.get_unread_count(db)}


@router.patch(
    "/{id}/read",
    response_model=ContactMessageAdminRow,
    summary="Mark inquiry as read or unread",
    description=ADMIN_ONLY,
)
@router.patch(
    "/{id}/read/",
    response_model=ContactMessageAdminRow,
    include_in_schema=False,
)
def mark_notification_read(
    id: int,
    payload: ContactMessageUpdateRead | None = None,
    db: Session = Depends(get_db),
    _current_admin: User = Depends(get_current_superuser),
) -> ContactMessageAdminRow:
    is_read = payload.is_read if payload is not None else True
    message = contact_crud.mark_contact_message_read(db, id, is_read=is_read)
    if not message:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Inquiry not found"
        )
    return message


@router.delete(
    "/{id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a contact inquiry",
    description=ADMIN_ONLY,
)
@router.delete(
    "/{id}/",
    status_code=status.HTTP_204_NO_CONTENT,
    include_in_schema=False,
)
def delete_notification(
    id: int,
    db: Session = Depends(get_db),
    _current_admin: User = Depends(get_current_superuser),
) -> None:
    deleted = contact_crud.delete_contact_message(db, id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Inquiry not found"
        )
