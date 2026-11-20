"""Structured JSON logging configuration for production environments.

Outputs standardized JSON logs with correlation IDs, timestamps, service names,
and automated scrubbing of sensitive credentials and candidate data.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
import logging
import re
import sys
from typing import Any

from app.core.config import settings

# Patterns to scrub from log messages
_TOKEN_SCRUB_PATTERNS = [
    (re.compile(r"(Bearer\s+)[A-Za-z0-9\-_\.=]+", re.IGNORECASE), r"\1[REDACTED_TOKEN]"),
    (re.compile(r'(password["\']?\s*[:=]\s*["\'])([^"\']+)(")', re.IGNORECASE), r'\1[REDACTED]\3'),
    (re.compile(r'(secret["\']?\s*[:=]\s*["\'])([^"\']+)(")', re.IGNORECASE), r'\1[REDACTED]\3'),
    (re.compile(r'(api_key["\']?\s*[:=]\s*["\'])([^"\']+)(")', re.IGNORECASE), r'\1[REDACTED]\3'),
]


def scrub_log_message(msg: str) -> str:
    """Sanitize secrets and tokens from raw log message text."""
    for pattern, repl in _TOKEN_SCRUB_PATTERNS:
        msg = pattern.sub(repl, msg)
    return msg


class JSONFormatter(logging.Formatter):
    """Formats log records as single-line JSON objects."""

    def __init__(self, service_name: str = "resume-analyzer-api"):
        super().__init__()
        self.service_name = service_name

    def format(self, record: logging.LogRecord) -> str:
        # Build structured dictionary
        timestamp = datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat()
        clean_msg = scrub_log_message(record.getMessage())

        log_data: dict[str, Any] = {
            "timestamp": timestamp,
            "level": record.levelname,
            "logger": record.name,
            "service": self.service_name,
            "environment": settings.SENTRY_ENVIRONMENT,
            "message": clean_msg,
        }

        # Include request_id if attached to record or extra
        request_id = getattr(record, "request_id", None)
        if request_id:
            log_data["request_id"] = request_id

        # Include exception traceback if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_data)


def configure_logging(service_name: str = "resume-analyzer-api") -> None:
    """Configure root logger to use JSON formatting or human-friendly console output."""
    use_json = (
        settings.LOG_FORMAT == "json"
        or (not settings.DEBUG and settings.LOG_FORMAT != "text")
    )

    root_logger = logging.getLogger()
    # Remove existing stream handlers to avoid duplicate output
    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)

    handler = logging.StreamHandler(sys.stdout)
    if use_json:
        handler.setFormatter(JSONFormatter(service_name=service_name))
    else:
        handler.setFormatter(
            logging.Formatter("%(asctime)s [%(levelname)s] [%(name)s] %(message)s")
        )

    root_logger.addHandler(handler)
    root_logger.setLevel(logging.DEBUG if settings.DEBUG else logging.INFO)

    # Keep noisy third-party libraries reasonably quiet
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("passlib").setLevel(logging.ERROR)
