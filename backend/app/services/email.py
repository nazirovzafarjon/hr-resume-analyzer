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
import logging
from typing import Any
from urllib.parse import quote

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

#: Resend REST endpoint for sending a single email.
RESEND_API_URL = "https://api.resend.com/emails"
#: Sandbox from-address every Resend account can send from.
DEFAULT_FROM = "onboarding@resend.dev"
#: Give the Resend API this long to answer before giving up.
_REQUEST_TIMEOUT_SECONDS = 20


def build_reset_link(token: str) -> str:
    """Absolute frontend URL a user clicks to reach the reset page.

    The token is URL-encoded so special characters survive transit inside the
    email HTML/text body.
    """
    base = settings.FRONTEND_BASE_URL.rstrip("/")
    return f"{base}/reset-password?token={quote(token, safe='')}"


def _configured_sender() -> str:
    """The from-address to use, falling back to the Resend sandbox default."""
    return settings.EMAIL_FROM.strip() or DEFAULT_FROM


def _api_key() -> str | None:
    """Configured Resend API key, or ``None`` when email sending is disabled."""
    return (settings.RESEND_API_KEY or "").strip() or None


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


def send_reset_password_email(email: str, token: str) -> bool:
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
    reset_link = build_reset_link(token)
    api_key = _api_key()
    if api_key is None:
        logger.warning(
            "Resend is not configured (RESEND_API_KEY missing) - reset email for "
            "%s not sent. Reset link: %s",
            email,
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

    try:
        response = httpx.post(
            RESEND_API_URL,
            headers={"Authorization": f"Bearer {api_key}"},
            json=payload,
            timeout=_REQUEST_TIMEOUT_SECONDS,
        )
    except httpx.HTTPError as exc:
        logger.error("Resend request failed for reset email to %s: %s", email, exc)
        return False

    if response.status_code >= 400:
        logger.error(
            "Resend rejected reset email for %s: HTTP %s %s",
            email,
            response.status_code,
            response.text,
        )
        return False

    logger.info(
        "Reset email accepted by Resend for %s (id=%s)",
        email,
        response.json().get("id") if response.content else None,
    )
    return True