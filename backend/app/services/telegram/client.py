"""Minimal synchronous Telegram Bot API client for outgoing notifications.

Celery workers send notifications through this module (plain ``httpx``), so
delivery never depends on the bot process being up. Failures are mapped to
exceptions the caller can act on:

* ``TelegramBlockedError`` (403) — the user blocked the bot or deleted the
  chat: stop sending, mark the link inactive.
* ``TelegramRetryAfterError`` (429) — rate limited: retry after the delay
  Telegram asks for.
* ``TelegramTransientError`` — 5xx or a network failure: retry with backoff.
* ``TelegramBadRequestError`` — any other 4xx: retrying cannot help.

The bot token is part of the URL path, so it is never logged.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

API_BASE = "https://api.telegram.org"
_TIMEOUT = httpx.Timeout(10.0, connect=5.0)


class TelegramError(Exception):
    """Base class for Bot API failures."""


class TelegramBlockedError(TelegramError):
    pass


class TelegramBadRequestError(TelegramError):
    pass


class TelegramTransientError(TelegramError):
    pass


class TelegramRetryAfterError(TelegramError):
    def __init__(self, retry_after: int) -> None:
        super().__init__(f"retry after {retry_after}s")
        self.retry_after = retry_after


def _call(method: str, payload: dict[str, Any]) -> dict[str, Any]:
    url = f"{API_BASE}/bot{settings.TELEGRAM_BOT_TOKEN}/{method}"
    try:
        response = httpx.post(url, json=payload, timeout=_TIMEOUT)
    except httpx.HTTPError as exc:
        raise TelegramTransientError(type(exc).__name__) from None

    try:
        body = response.json()
    except ValueError:
        body = {}
    if response.status_code == 200 and body.get("ok"):
        return body.get("result") or {}

    description = str(body.get("description") or response.reason_phrase)[:200]
    if response.status_code == 403:
        raise TelegramBlockedError(description)
    if response.status_code == 429:
        retry_after = int((body.get("parameters") or {}).get("retry_after") or 5)
        raise TelegramRetryAfterError(retry_after)
    if response.status_code >= 500:
        raise TelegramTransientError(f"{response.status_code}: {description}")
    raise TelegramBadRequestError(f"{response.status_code}: {description}")


def send_message(
    chat_id: int,
    text: str,
    *,
    buttons: list[list[dict[str, str]]] | None = None,
) -> dict[str, Any]:
    """Send an HTML message. ``buttons`` are rows of inline keyboard buttons."""
    payload: dict[str, Any] = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    if buttons:
        payload["reply_markup"] = {"inline_keyboard": buttons}
    return _call("sendMessage", payload)
