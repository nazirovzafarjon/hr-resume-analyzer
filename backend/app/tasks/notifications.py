"""Celery background tasks for transactional notifications and emails.

Workloads are routed to the dedicated ``notifications`` queue to prevent email
delivery delays caused by compute-heavy AI inference queues.
"""

from __future__ import annotations

import logging
from typing import Any

from celery import Task
import httpx

from app.core.celery_app import celery_app
from app.services import email as email_service

logger = logging.getLogger(__name__)

# Transient HTTP status codes from email providers (Resend) that warrant Celery retry
_RETRYABLE_EMAIL_STATUS_CODES = {429, 500, 502, 503, 504}


@celery_app.task(
    bind=True,
    name="app.tasks.notifications.send_email_task",
    max_retries=3,
    default_retry_delay=5,
    acks_late=True,
)
def send_email_task(
    self: Task,
    email_type: str,
    recipient: str,
    **kwargs: Any,
) -> dict[str, Any]:
    """Deliver a transactional email via Resend in the background.

    Args:
        self: Celery Task instance for retry handling.
        email_type: Type of email ('hr_registration', 'verification_code', 'reset_password', 'verification_link').
        recipient: Destination email address.
        **kwargs: Parameters needed for the specific email type (e.g., token, code, path).

    Returns:
        dict summary of delivery outcome.
    """
    logger.info(
        "Celery task send_email_task[id=%s, type=%s, to=%s]",
        self.request.id,
        email_type,
        email_service._mask_email(recipient),
    )

    try:
        if email_type == "hr_registration":
            from app.services import auth as auth_service

            token = kwargs.get("token", "")
            code = kwargs.get("code") or ""
            auth_service.dispatch_registration_email(recipient, token, code)
            success = True
            message_id = None
            error = None

        elif email_type == "verification_code":
            code = kwargs.get("code", "")
            result = email_service.send_verification_code_email(recipient, code=code)
            success = result.success
            message_id = result.message_id
            error = result.error

        elif email_type == "reset_password":
            token = kwargs.get("token", "")
            path = kwargs.get("path", "/reset-password")
            success = email_service.send_reset_password_email(recipient, token=token, path=path)
            message_id = None
            error = None if success else "Password reset email delivery returned False"

        elif email_type == "verification_link":
            token = kwargs.get("token", "")
            path = kwargs.get("path", "/verify-email")
            success = email_service.send_verification_email(recipient, token=token, path=path)
            message_id = None
            error = None if success else "Verification email delivery returned False"

        else:
            logger.warning("Unsupported email_type=%s; task aborting", email_type)
            return {
                "status": "unsupported_type",
                "email_type": email_type,
                "recipient": recipient,
            }

        if success:
            logger.info(
                "Email sent successfully: type=%s to=%s message_id=%s",
                email_type,
                email_service._mask_email(recipient),
                message_id,
            )
            return {
                "status": "delivered",
                "email_type": email_type,
                "recipient": recipient,
                "message_id": message_id,
            }

        logger.warning(
            "Email delivery failed: type=%s to=%s error=%s",
            email_type,
            email_service._mask_email(recipient),
            error,
        )
        return {
            "status": "failed",
            "email_type": email_type,
            "recipient": recipient,
            "error": error,
        }

    except (httpx.TimeoutException, httpx.NetworkError) as exc:
        if self.request.retries < self.max_retries:
            retry_delay = 5 * (2 ** self.request.retries)
            logger.warning(
                "Transient network error delivering email. Retrying in %ss: %s",
                retry_delay,
                exc,
            )
            raise self.retry(exc=exc, countdown=retry_delay)
        logger.error(
            "Email delivery failed after max retries: type=%s to=%s error=%s",
            email_type,
            recipient,
            exc,
        )
        return {
            "status": "failed",
            "email_type": email_type,
            "recipient": recipient,
            "error": str(exc),
        }
    except Exception as exc:
        logger.exception("Unexpected exception in send_email_task: %s", exc)
        return {
            "status": "unexpected_error",
            "email_type": email_type,
            "recipient": recipient,
            "error": str(exc),
        }


@celery_app.task(
    bind=True,
    name="app.tasks.notifications.send_telegram_task",
    max_retries=5,
    acks_late=True,
)
def send_telegram_task(self: Task, **payload: Any) -> dict[str, Any]:
    """Deliver one queued Telegram notification (see ``services.telegram.notifier``).

    The message is rendered now, from current data, in the chat's language.
    A blocked bot (403) deactivates the link; rate limits and transient
    failures are retried; other Bot API rejections are logged and dropped.
    """
    from app.core.database import SessionLocal
    from app.services.telegram import client, notifier

    with SessionLocal() as db:
        message = notifier.build_message(db, payload)
        if message is None:
            return {"status": "skipped"}
        try:
            client.send_message(message.chat_id, message.text, buttons=message.buttons)
        except client.TelegramBlockedError:
            notifier.mark_blocked(db, message.link_id)
            logger.info("Telegram link id=%s blocked the bot; deactivated", message.link_id)
            return {"status": "blocked"}
        except client.TelegramRetryAfterError as exc:
            raise self.retry(exc=exc, countdown=exc.retry_after)
        except client.TelegramTransientError as exc:
            if self.request.retries < self.max_retries:
                raise self.retry(exc=exc, countdown=5 * (2 ** self.request.retries))
            logger.error("Telegram delivery failed after retries: %s", exc)
            return {"status": "failed", "error": str(exc)}
        except client.TelegramBadRequestError as exc:
            logger.error("Telegram rejected the message for link id=%s: %s", message.link_id, exc)
            return {"status": "rejected", "error": str(exc)}
    return {"status": "sent"}
