"""Transactional email delivery through the Resend REST API.

Resend (https://resend.com) powers the password-reset workflow. Messages are
posted straight to ``POST https://api.resend.com/emails`` with ``httpx`` — the
HTTP client the app already depends on — instead of the official ``resend``
SDK. That keeps a single HTTP-client dependency and works on Python 3.14, where
the SDK has not shipped a compatible release yet.

Configuration (``backend/.env`` or environment variables, see
:mod:`app.core.config`):

* ``RESEND_API_KEY`` — secret key from https://resend.com/api-keys
* ``EMAIL_FROM`` — verified sender address; defaults to the ``onboarding@resend.dev``
  sandbox sender every Resend account ships with (it may only deliver to the
  address the account was registered with)
* ``FRONTEND_BASE_URL`` — frontend origin used to build the absolute reset link
* ``PASSWORD_RESET_TOKEN_EXPIRE_MINUTES`` — advertised link lifetime in the body

Failure handling is deliberately non-fatal: a missing API key or a failed
request is logged loudly and reported to the caller as ``False``. Callers such
as the auth service keep answering with a *generic* success message (never
revealing whether an address is registered) and fall back to logging the reset
link for development.
"""

import html
import json
import logging
import re
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

#: Resend REST endpoint for sending a single email.
RESEND_API_URL = "https://api.resend.com/emails"
#: Sandbox from-address every Resend account can send from.
DEFAULT_FROM = "onboarding@resend.dev"

#: Provider status codes worth retrying: a rate limit or a transient server
#: fault. 4xx (validation, sandbox 403, auth) are permanent — retrying a 403
#: like Resend's sandbox restriction can never succeed.
_RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}

#: Matches e-mail addresses inside a provider error body so they can be
#: redacted before the message reaches the server log.
_EMAIL_ADDRESS_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")


def _mask_email(email: str) -> str:
    """Mask the local part of an address for logs (``hr@x.com`` -> ``h***@x.com``)."""
    local, _, domain = email.partition("@")
    if not domain:
        return "***"
    return f"{local[:1]}***@{domain}"


@dataclass
class EmailDeliveryResult:
    """Outcome of an email delivery attempt through the provider."""

    success: bool
    message_id: str | None = None
    error: str | None = None
    status_code: int | None = None

    def __bool__(self) -> bool:
        return self.success


def build_reset_link(token: str, path: str = "/reset-password") -> str:
    """Absolute frontend URL a user clicks to reach the reset page.

    The token is URL-encoded so special characters survive transit inside the
    email HTML/text body. ``path`` selects the page (the Candidate Portal uses
    ``/candidate/reset-password``).
    """
    base = settings.FRONTEND_BASE_URL.rstrip("/")
    return f"{base}{path}?token={quote(token, safe='')}"


def build_verify_email_link(token: str, path: str = "/verify-email") -> str:
    """Absolute frontend URL a user clicks to verify their email.

    Mirrors :func:`build_reset_link`: the token is URL-encoded and the origin
    comes from the configured ``FRONTEND_BASE_URL`` (never hardcoded). The
    Candidate Portal uses ``/candidate/verify-email``.
    """
    base = settings.FRONTEND_BASE_URL.rstrip("/")
    return f"{base}{path}?token={quote(token, safe='')}"


def _configured_sender() -> str:
    """The from-address to use, falling back to the Resend sandbox default.

    When ``EMAIL_FROM_NAME`` is set and ``EMAIL_FROM`` is a bare address, the
    sender is rendered in RFC 5322 form (``"Name <addr@domain>"``), which Resend
    accepts. A value that already contains ``<…>`` is passed through unchanged.
    """
    address = settings.EMAIL_FROM.strip() or DEFAULT_FROM
    name = settings.EMAIL_FROM_NAME.strip()
    if name and "<" not in address:
        return f"{name} <{address}>"
    return address


def _reply_to() -> str | None:
    """Configured Reply-To address, or ``None`` when unset."""
    return settings.EMAIL_REPLY_TO.strip() or None


def _api_key() -> str | None:
    """Configured Resend API key, or ``None`` when email sending is disabled."""
    return (settings.RESEND_API_KEY or "").strip() or None


def _sanitize_provider_message(text: str | None) -> str:
    """Reduce a provider error body to a short, PII-free summary for logs.

    Resend returns JSON such as ``{"statusCode":403,"message":"You can only
    send testing emails to your own email address (owner@example.com)…",
    "name":"validation_error"}``. The body embeds real addresses, so it must
    never be logged verbatim: the address(es) are redacted and the value is
    truncated. Only the ``name``/``message`` fields are kept.
    """
    if not text:
        return ""
    message = text.strip()
    try:
        data = json.loads(message)
    except (ValueError, TypeError):
        data = None
    if isinstance(data, dict):
        kept = [str(data[field]) for field in ("name", "message") if data.get(field)]
        if kept:
            message = " ".join(kept)
    return _EMAIL_ADDRESS_RE.sub("<redacted-email>", message)[:300]


def _error_detail_for(status_code: int, text: str | None, sender: str) -> str:
    """Map a provider rejection to a safe, actionable caller-facing message.

    Never reflects the raw provider body (it contains addresses and provider
    internals); the detail is a fixed, human-readable explanation instead.
    """
    body = (text or "").lower()
    if (
        "only send testing emails to your own email address" in body
        or "verify a domain" in body
        or ("onboarding@resend.dev" in sender and status_code == 403)
    ):
        return (
            "The email provider rejected delivery. When using Resend's onboarding sandbox, "
            "emails can only be sent to the registered Resend account owner. "
            "Please verify a custom domain in Resend to send to arbitrary addresses."
        )
    if status_code == 401:
        return "Email provider rejected authentication (invalid or restricted API key)."
    if status_code == 403:
        return "Email provider rejected delivery (sender is not authorized to send to this address)."
    if status_code == 422:
        return "Email provider rejected request parameters."
    if status_code == 429:
        return "Email provider rate limit reached. Please try again later."
    return "Email provider rejected delivery."


def _backoff_seconds(attempt: int) -> float:
    """Bounded exponential backoff for retry ``attempt`` (0-based)."""
    base = max(0.0, float(settings.EMAIL_RETRY_BASE_DELAY))
    delay = base * (2**attempt)
    return min(delay, max(0.0, float(settings.EMAIL_MAX_RETRY_WAIT)))


def _post_email(payload: dict[str, Any], *, context: str) -> EmailDeliveryResult:
    """POST one message to Resend, retrying only transient failures.

    Returns an :class:`EmailDeliveryResult`. Transient failures (HTTP 429/5xx,
    a network error or a connection timeout) are retried up to
    ``EMAIL_MAX_RETRIES`` times with bounded exponential backoff; permanent 4xx
    rejections and read timeouts fail immediately. Provider error bodies are
    sanitized before being logged; a live API key is never logged.
    """
    api_key = _api_key()
    if api_key is None:  # Defensive: callers check first, but never leak a request.
        return EmailDeliveryResult(
            success=False, error="Email service is not configured."
        )

    max_retries = max(0, settings.EMAIL_MAX_RETRIES)
    sender = _configured_sender()
    # Inject the optional Reply-To once, for every message kind.
    reply_to = _reply_to()
    if reply_to and "reply_to" not in payload:
        payload = {**payload, "reply_to": reply_to}
    attempt = 0
    while True:
        try:
            response = httpx.post(
                RESEND_API_URL,
                headers={"Authorization": f"Bearer {api_key}"},
                json=payload,
                timeout=settings.EMAIL_REQUEST_TIMEOUT,
            )
        except httpx.TimeoutException as exc:
            # A read timeout is not obviously transient and retrying would only
            # multiply the delay; fail fast with a safe message.
            logger.error("Resend request timed out (%s): %s", context, type(exc).__name__)
            return EmailDeliveryResult(
                success=False,
                error="The email provider did not respond in time. Please try again later.",
            )
        except httpx.HTTPError as exc:
            if attempt < max_retries:
                _sleep_backoff(attempt)
                attempt += 1
                continue
            logger.error("Resend request failed (%s): %s", context, type(exc).__name__)
            return EmailDeliveryResult(
                success=False,
                error="Unable to connect to email provider. Please try again later.",
            )

        if response.status_code < 400:
            message_id = None
            if response.content:
                try:
                    message_id = response.json().get("id")
                except (ValueError, TypeError):
                    message_id = None
            logger.info(
                "Resend accepted %s (id=%s)", context, message_id
            )
            return EmailDeliveryResult(
                success=True,
                message_id=message_id,
                status_code=response.status_code,
            )

        if response.status_code in _RETRYABLE_STATUS_CODES and attempt < max_retries:
            logger.warning(
                "Resend transient failure for %s (HTTP %s); retrying",
                context,
                response.status_code,
            )
            _sleep_backoff(attempt)
            attempt += 1
            continue

        logger.error(
            "Resend rejected %s: HTTP %s %s",
            context,
            response.status_code,
            _sanitize_provider_message(response.text),
        )
        return EmailDeliveryResult(
            success=False,
            error=_error_detail_for(response.status_code, response.text, sender),
            status_code=response.status_code,
        )


def _sleep_backoff(attempt: int) -> None:
    """Sleep for the backoff before retry ``attempt`` (patched in tests)."""
    time.sleep(_backoff_seconds(attempt))


def log_development_link(message: str, link: str) -> None:
    """Log a token-bearing fallback link only in DEBUG builds.

    When email delivery is unavailable, development needs the link to keep the
    flow testable. In production the link embeds a live credential, so it is
    never written to the log: only a delivery-failure warning is emitted, which
    avoids leaking a usable reset/verification token to log aggregators.
    """
    if settings.DEBUG:
        logger.warning("%s Development link: %s", message, link)
    else:
        logger.error(
            "%s Email delivery is unavailable; the credential link was not logged.",
            message,
        )


def _render_reset_html(reset_link: str) -> str:
    """Inline-styled HTML body for the reset email (no external assets).

    Only the reset link is interpolated; it is HTML-escaped so a hostile token
    cannot smuggle markup into the message.
    """
    link = html.escape(reset_link, quote=True)

    return f"""\
<!doctype html>
<html lang="en">
  <head><meta charset="utf-8" /></head>
  <body style="margin:0;padding:0;background-color:#f4f4f5">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
           style="background-color:#f4f4f5">
      <tr>
        <td align="center" style="padding:32px 8px">
          <table role="presentation" width="560" cellpadding="0" cellspacing="0"
                 style="background-color:#ffffff;border-radius:8px;border:1px solid #e0e0e0">
            <tr>
              <td style="padding:28px 32px">
                <h1 style="margin:0 0 16px;font-size:22px;color:#1f2937">
                  Reset your password
                </h1>
                <p style="margin:0 0 16px;font-size:15px;line-height:1.5;color:#374151">
                  We received a request to reset your Resume Analyzer password.
                  Open the link below to choose a new password — or keep your
                  current one and sign in straight away.
                </p>
                <p style="margin:0 0 20px">
                  <a href="{link}"
                     style="display:inline-block;padding:12px 20px;border-radius:6px;
                            background-color:#2563eb;color:#ffffff;font-size:15px;
                            text-decoration:none;font-weight:600">
                    Reset your password
                  </a>
                </p>
                <p style="margin:0 0 12px;font-size:13px;line-height:1.5;color:#6b7280">
                  Or copy this link into your browser:<br />
                  <span style="word-break:break-all;font-family:monospace;font-size:12px">{link}</span>
                </p>
                <p style="margin:0;font-size:13px;line-height:1.5;color:#6b7280">
                  This link expires in {settings.PASSWORD_RESET_TOKEN_EXPIRE_MINUTES} minutes.
                  If you did not request a reset, you can safely ignore this email.
                </p>
              </td>
            </tr>
          </table>
        </td>
      </tr>
    </table>
  </body>
</html>"""


def _render_verify_html(verify_link: str) -> str:
    """Inline-styled HTML body for the "Verify your email" message."""
    link = html.escape(verify_link, quote=True)
    return f"""\
<!doctype html>
<html lang="en">
  <head><meta charset="utf-8" /></head>
  <body style="margin:0;padding:0;background-color:#f4f4f5">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
           style="background-color:#f4f4f5">
      <tr>
        <td align="center" style="padding:32px 8px">
          <table role="presentation" width="560" cellpadding="0" cellspacing="0"
                 style="background-color:#ffffff;border-radius:8px;border:1px solid #e0e0e0">
            <tr>
              <td style="padding:28px 32px">
                <h1 style="margin:0 0 16px;font-size:22px;color:#1f2937">
                  Verify your email
                </h1>
                <p style="margin:0 0 16px;font-size:15px;line-height:1.5;color:#374151">
                  Confirm this email address to continue creating your Resume
                  Analyzer panel. Email verification is required before the HR
                  or Candidate panel can be used.
                </p>
                <p style="margin:0 0 20px">
                  <a href="{link}"
                     style="display:inline-block;padding:12px 20px;border-radius:6px;
                            background-color:#2563eb;color:#ffffff;font-size:15px;
                            text-decoration:none;font-weight:600">
                    Verify my email
                  </a>
                </p>
                <p style="margin:0 0 12px;font-size:13px;line-height:1.5;color:#6b7280">
                  Or copy this link into your browser:<br />
                  <span style="word-break:break-all;font-family:monospace;font-size:12px">{link}</span>
                </p>
                <p style="margin:0;font-size:13px;line-height:1.5;color:#6b7280">
                  This link expires in {settings.PASSWORD_RESET_TOKEN_EXPIRE_MINUTES} minutes.
                  If you did not create an account, you can safely ignore this email.
                </p>
              </td>
            </tr>
          </table>
        </td>
      </tr>
    </table>
  </body>
</html>"""


def send_verification_email(email: str, token: str, path: str = "/verify-email") -> bool:
    """Send the "Verify your email" message for ``token`` to ``email``.

    Reuses the exact Resend plumbing as password reset: returns ``True`` when
    Resend accepted it, ``False`` (with the reason logged) when email is
    unconfigured or fails, so callers can fall back to logging the link in
    development while keeping a generic response.
    """
    verify_link = build_verify_email_link(token, path)
    api_key = _api_key()
    if api_key is None:
        log_development_link(
            f"Verification email for {_mask_email(email)} not sent (RESEND_API_KEY missing).",
            verify_link,
        )
        return False

    payload: dict[str, Any] = {
        "from": _configured_sender(),
        "to": [email],
        "subject": "Verify your email",
        "html": _render_verify_html(verify_link),
        "text": (
            "Confirm this email address to continue creating your Resume "
            "Analyzer panel. Email verification is required before the HR or "
            "Candidate panel can be used.\n\n"
            f"{verify_link}\n\n"
            f"This link expires in {settings.PASSWORD_RESET_TOKEN_EXPIRE_MINUTES} "
            "minutes. If you did not create an account, you can safely ignore this "
            "email."
        ),
    }

    return _post_email(payload, context=f"verification email for {_mask_email(email)}").success


def _render_hr_verify_html(verify_link: str, code: str | None = None, minutes: int = 10) -> str:
    """Inline-styled HTML body for HR two-phase registration email."""
    link = html.escape(verify_link, quote=True)
    code_block = ""
    if code:
        safe_code = html.escape(code, quote=True)
        code_block = f"""\
                <p style="margin:20px 0 8px;font-size:14px;color:#4b5563">
                  Or use this 6-digit confirmation code:
                </p>
                <p style="margin:0 0 20px;font-size:28px;font-weight:700;letter-spacing:6px;color:#2563eb;font-family:monospace">
                  {safe_code}
                </p>"""
    return f"""\
<!doctype html>
<html lang="en">
  <head><meta charset="utf-8" /></head>
  <body style="margin:0;padding:0;background-color:#f4f4f5">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
           style="background-color:#f4f4f5">
      <tr>
        <td align="center" style="padding:32px 8px">
          <table role="presentation" width="560" cellpadding="0" cellspacing="0"
                 style="background-color:#ffffff;border-radius:8px;border:1px solid #e0e0e0">
            <tr>
              <td style="padding:28px 32px">
                <h1 style="margin:0 0 16px;font-size:22px;color:#1f2937">
                  Verify your email — Resume Analyzer
                </h1>
                <p style="margin:0 0 16px;font-size:15px;line-height:1.5;color:#374151">
                  Thank you for registering. Confirm your email address to complete creating your
                  Resume Analyzer account. Email verification is required before the HR panel can be used.
                </p>
                <p style="margin:0 0 20px">
                  <a href="{link}"
                     style="display:inline-block;padding:12px 24px;border-radius:6px;
                            background-color:#2563eb;color:#ffffff;font-size:15px;
                            text-decoration:none;font-weight:600">
                    It's me — Verify Email
                  </a>
                </p>
{code_block}
                <p style="margin:0 0 12px;font-size:13px;line-height:1.5;color:#6b7280">
                  Or copy this link into your browser:<br />
                  <span style="word-break:break-all;font-family:monospace;font-size:12px">{link}</span>
                </p>
                <p style="margin:0;font-size:13px;line-height:1.5;color:#6b7280">
                  This link expires in {minutes} minutes. If you did not create an account, you can safely ignore this email.
                </p>
              </td>
            </tr>
          </table>
        </td>
      </tr>
    </table>
  </body>
</html>"""


def send_hr_registration_email(
    email: str, token: str, code: str | None = None, path: str = "/verify-email"
) -> EmailDeliveryResult:
    """Send HR two-phase registration email containing verification link and code."""
    minutes = settings.EMAIL_VERIFICATION_CODE_EXPIRE_MINUTES
    verify_link = build_verify_email_link(token, path)
    api_key = _api_key()
    if api_key is None:
        log_development_link(
            f"Verification email for {_mask_email(email)} not sent (RESEND_API_KEY missing).",
            verify_link,
        )
        return EmailDeliveryResult(
            success=False,
            error="Email service is not configured (RESEND_API_KEY is missing).",
        )

    sender = _configured_sender()
    text_content = (
        "Verify your email — Resume Analyzer\n\n"
        "Confirm your email address to complete creating your Resume Analyzer account.\n\n"
        f"Verification Link: {verify_link}\n\n"
    )
    if code:
        text_content += f"Confirmation Code: {code}\n\n"
    text_content += (
        f"This link expires in {minutes} minutes. If you did not create an account, "
        "you can safely ignore this email."
    )

    payload: dict[str, Any] = {
        "from": sender,
        "to": [email],
        "subject": "Verify Your Email — Resume Analyzer",
        "html": _render_hr_verify_html(verify_link, code, minutes),
        "text": text_content,
    }

    return _post_email(payload, context=f"registration verification email for {_mask_email(email)}")


def _render_verify_code_html(code: str, minutes: int) -> str:
    """Inline-styled HTML body for the 6-digit verification-code email."""
    safe_code = html.escape(code, quote=True)
    return f"""\
<!doctype html>
<html lang="en">
  <head><meta charset="utf-8" /></head>
  <body style="margin:0;padding:0;background-color:#f4f4f5">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
           style="background-color:#f4f4f5">
      <tr>
        <td align="center" style="padding:32px 8px">
          <table role="presentation" width="560" cellpadding="0" cellspacing="0"
                 style="background-color:#ffffff;border-radius:8px;border:1px solid #e0e0e0">
            <tr>
              <td style="padding:28px 32px">
                <h1 style="margin:0 0 16px;font-size:22px;color:#1f2937">
                  Verify Your Email — Resume Analyzer
                </h1>
                <p style="margin:0 0 16px;font-size:15px;line-height:1.5;color:#374151">
                  You received this email because an account was registered with this
                  email address on Resume Analyzer. Enter this 6-digit verification
                  code to confirm your email and activate your account:
                </p>
                <p style="margin:0 0 20px;font-size:32px;font-weight:700;
                          letter-spacing:8px;color:#2563eb;font-family:monospace">
                  {safe_code}
                </p>
                <p style="margin:0 0 12px;font-size:13px;line-height:1.5;color:#6b7280">
                  This code expires in {minutes} minutes. If you did not create an
                  account, you can safely ignore this email.
                </p>
              </td>
            </tr>
          </table>
        </td>
      </tr>
    </table>
  </body>
</html>"""


def send_verification_code_email(email: str, code: str) -> EmailDeliveryResult:
    """Send the 6-digit email-verification code to ``email`` via Resend.

    The raw code appears only inside the delivered message — never in logs or
    API responses. Returns an :class:`EmailDeliveryResult` detailing provider
    acceptance or failure.
    """
    minutes = settings.EMAIL_VERIFICATION_CODE_EXPIRE_MINUTES
    api_key = _api_key()
    if api_key is None:
        logger.warning(
            "Resend is not configured (RESEND_API_KEY missing) - verification "
            "code email for %s not sent.",
            _mask_email(email),
        )
        return EmailDeliveryResult(
            success=False,
            error="Email service is not configured (RESEND_API_KEY is missing).",
        )

    sender = _configured_sender()
    payload: dict[str, Any] = {
        "from": sender,
        "to": [email],
        "subject": "Verify Your Email — Resume Analyzer",
        "html": _render_verify_code_html(code, minutes),
        "text": (
            "Verify Your Email — Resume Analyzer\n\n"
            "You received this email because an account was registered with this "
            "email address on Resume Analyzer.\n\n"
            f"Your 6-digit verification code is:\n\n{code}\n\n"
            f"This code expires in {minutes} minutes.\n\n"
            "If you did not create this account, you can ignore this email."
        ),
    }

    return _post_email(payload, context=f"verification code email for {_mask_email(email)}")


def send_reset_password_email(email: str, token: str, path: str = "/reset-password") -> bool:
    """Send the "Reset Your Password" email for ``token`` to ``email``.

    Builds the one-click reset link from ``FRONTEND_BASE_URL``, renders the HTML
    body and posts it to the Resend API with the configured sender.

    Returns:
        ``True`` when Resend accepted the email for delivery (HTTP 2xx).
        ``False`` — with the reason logged — when no API key is configured or
        the request failed. Callers fall back to logging the link.

    Failures are logged, never raised, so the forgot-password endpoint can keep
    its identical response for every address (no account enumeration).
    """
    reset_link = build_reset_link(token, path)
    api_key = _api_key()
    if api_key is None:
        log_development_link(
            f"Reset email for {_mask_email(email)} not sent (RESEND_API_KEY missing).",
            reset_link,
        )
        return False

    payload: dict[str, Any] = {
        "from": _configured_sender(),
        "to": [email],
        "subject": "Reset Your Password",
        "html": _render_reset_html(reset_link),
        "text": (
            "We received a request to reset your Resume Analyzer password.\n\n"
            "Open the link below to choose a new password — or keep your current "
            "one and sign in straight away:\n\n"
            f"{reset_link}\n\n"
            f"This link expires in {settings.PASSWORD_RESET_TOKEN_EXPIRE_MINUTES} "
            "minutes. If you did not request a reset, you can safely ignore this "
            "email."
        ),
    }

    return _post_email(payload, context=f"password reset email for {_mask_email(email)}").success