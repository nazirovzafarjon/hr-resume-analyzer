"""Pydantic schemas for the public Contact Us form."""

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, EmailStr, StringConstraints

#: Names are trimmed first, so a value of only spaces counts as missing.
NameStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
MessageStr = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=5000)
]


class ContactMessageCreate(BaseModel):
    """Payload posted by the landing page's Contact form."""

    first_name: NameStr
    last_name: NameStr
    email: EmailStr
    subject: str | None = None
    message: MessageStr


class ContactMessageResult(BaseModel):
    """Public acknowledgement: never echoes stored data or internal ids."""

    message: str = "Thanks for reaching out! We'll get back to you soon."


class ContactMessageAdminRow(BaseModel):
    """Admin representation of a contact inquiry."""

    id: int
    name: str
    first_name: str
    last_name: str
    email: str
    subject: str | None = None
    message: str
    is_read: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ContactMessagePage(BaseModel):
    """Paginated list of contact inquiries with unread count."""

    items: list[ContactMessageAdminRow]
    total: int
    unread_count: int
    page: int
    limit: int


class ContactMessageUpdateRead(BaseModel):
    """Payload for updating read status."""

    is_read: bool = True


class ContactUnreadCount(BaseModel):
    """Unread inquiries count for badges."""

    unread_count: int
