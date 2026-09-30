"""Pydantic schemas for the public Contact Us form."""

from typing import Annotated

from pydantic import BaseModel, EmailStr, StringConstraints

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
    message: MessageStr


class ContactMessageResult(BaseModel):
    """Public acknowledgement: never echoes stored data or internal ids."""

    message: str = "Thanks for reaching out! We'll get back to you soon."
