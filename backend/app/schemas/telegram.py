"""Schemas for the Telegram account-linking endpoints."""

from datetime import datetime

from pydantic import BaseModel


class TelegramLinkStatus(BaseModel):
    """Whether the bot is available and, if linked, which Telegram account."""

    #: False when the server has no bot configured (the UI hides the card).
    enabled: bool
    linked: bool
    bot_username: str | None = None
    username: str | None = None
    first_name: str | None = None
    linked_at: datetime | None = None
    #: False after Telegram reported that the user blocked the bot.
    is_active: bool | None = None


class TelegramLinkToken(BaseModel):
    """A single-use deep link that opens the bot and links this account."""

    deep_link: str
    expires_at: datetime
