"""Pydantic schemas for the Help Center support chat."""

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, StringConstraints

#: Trimmed first, so a message of only spaces counts as empty.
MessageBody = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4000)]
PageUrl = Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)]

ConversationStatus = Literal["open", "closed"]
RequesterKind = Literal["hr", "candidate"]
Sender = Literal["requester", "admin"]


class SupportConversationCreate(BaseModel):
    """First message of a new conversation, sent from the Help button."""

    body: MessageBody
    #: Portal path the requester was on (helps the admin reproduce the problem).
    page_url: PageUrl | None = None


class SupportMessageCreate(BaseModel):
    body: MessageBody


class SupportMessageRead(BaseModel):
    """A message as shown in the chat (both sides see the same fields)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    sender: Sender
    author_name: str | None = None
    body: str
    created_at: datetime


class SupportConversationSummary(BaseModel):
    """A conversation as the requester sees it in their own list."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    status: ConversationStatus
    created_at: datetime
    last_message_at: datetime
    closed_at: datetime | None = None
    unread_count: int = 0


class SupportConversationDetail(SupportConversationSummary):
    messages: list[SupportMessageRead]


class SupportUnreadCount(BaseModel):
    unread_count: int


# --- Admin ---------------------------------------------------------------


class SupportAdminConversationRow(BaseModel):
    """One row of the admin Support inbox."""

    id: int
    status: ConversationStatus
    requester_kind: RequesterKind
    requester_name: str
    requester_email: str
    preview: str
    message_count: int
    unread_count: int
    created_at: datetime
    last_message_at: datetime
    closed_at: datetime | None = None


class SupportAdminConversationPage(BaseModel):
    items: list[SupportAdminConversationRow]
    total: int
    page: int
    limit: int


class SupportAdminConversationDetail(SupportAdminConversationRow):
    page_url: str | None = None
    closed_by_name: str | None = None
    #: Id of the requester's account (HR user or candidate), for a profile link.
    requester_id: int | None = None
    messages: list[SupportMessageRead]
