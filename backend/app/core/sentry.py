"""Sentry error tracking integration with data scrubbing and privacy protection.

Sentry integration is entirely optional: if SENTRY_DSN is not configured,
this module safely no-ops without degrading application performance or startup.
"""

from __future__ import annotations

import logging
from typing import Any

from app.core.config import settings

logger = logging.getLogger(__name__)

# Sensitive header keys that must never be sent to Sentry
_SCRUB_HEADERS = {
    "authorization",
    "proxy-authorization",
    "cookie",
    "set-cookie",
    "x-api-key",
    "api-key",
}

# Sensitive payload keys that must be redacted
_SENSITIVE_FIELD_NAMES = {
    "password",
    "current_password",
    "new_password",
    "hashed_password",
    "token",
    "access_token",
    "refresh_token",
    "secret",
    "secret_key",
    "api_key",
    "ai_api_key",
    "credential",
    "resume_content",
    "vacancy_content",
    "raw_resume",
}


def _scrub_dict(data: dict[str, Any]) -> dict[str, Any]:
    """Recursively redact sensitive fields from dictionaries."""
    sanitized: dict[str, Any] = {}
    for key, value in data.items():
        lower_key = str(key).lower()
        if lower_key in _SENSITIVE_FIELD_NAMES or any(s in lower_key for s in ("password", "secret", "token")):
            sanitized[key] = "[REDACTED]"
        elif isinstance(value, dict):
            sanitized[key] = _scrub_dict(value)
        elif isinstance(value, list):
            sanitized[key] = [
                _scrub_dict(item) if isinstance(item, dict) else item
                for item in value
            ]
        else:
            sanitized[key] = value
    return sanitized


def _before_send(event: dict[str, Any], hint: dict[str, Any]) -> dict[str, Any] | None:
    """Filter and sanitize event payload before dispatching to Sentry."""
    request_data = event.get("request")
    if request_data and isinstance(request_data, dict):
        # Scrub HTTP headers
        headers = request_data.get("headers")
        if isinstance(headers, dict):
            for h in list(headers.keys()):
                if h.lower() in _SCRUB_HEADERS:
                    headers[h] = "[REDACTED]"

        # Scrub request body payload
        body = request_data.get("data")
        if isinstance(body, dict):
            request_data["data"] = _scrub_dict(body)

    # Scrub extra contexts
    extra = event.get("extra")
    if isinstance(extra, dict):
        event["extra"] = _scrub_dict(extra)

    return event


def init_sentry() -> bool:
    """Initialize Sentry SDK if configured. Returns True if initialized."""
    dsn = settings.SENTRY_DSN.strip()
    if not dsn:
        logger.info("Sentry DSN not configured; error tracking disabled.")
        return False

    try:
        import sentry_sdk
        from sentry_sdk.integrations.celery import CeleryIntegration
        from sentry_sdk.integrations.fastapi import FastApiIntegration

        sentry_sdk.init(
            dsn=dsn,
            environment=settings.SENTRY_ENVIRONMENT,
            release=settings.SENTRY_RELEASE or None,
            traces_sample_rate=settings.SENTRY_TRACES_SAMPLE_RATE,
            send_default_pii=False,  # Enforce strict privacy
            before_send=_before_send,
            integrations=[
                FastApiIntegration(transaction_style="endpoint"),
                CeleryIntegration(),
            ],
        )
        logger.info(
            "Sentry initialized successfully [env=%s, release=%s]",
            settings.SENTRY_ENVIRONMENT,
            settings.SENTRY_RELEASE,
        )
        return True
    except Exception as exc:
        logger.warning("Failed to initialize Sentry: %s", exc)
        return False
