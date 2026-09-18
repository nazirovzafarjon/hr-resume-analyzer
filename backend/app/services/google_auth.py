"""Google OAuth 2.0 (Sign in with Google) service.

Implements the server-side half of the authorization-code flow:

1. ``exchange_code_for_tokens`` swaps the one-time authorization ``code``
   (received from the frontend) for Google access/id tokens.
2. ``fetch_user_info`` loads the user's profile (email, name, picture, sub)
   from Google's userinfo endpoint.

All HTTP calls use ``httpx`` with an injected client so tests can substitute
a stub. Every failure path raises :class:`GoogleAuthError` with a
user-presentable message; network/timeout errors are converted too, so the
endpoint layer never sees raw ``httpx`` exceptions.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"

_GOOGLE_TIMEOUT_SECONDS = 10.0

#: Google's JS-initiated OAuth flow (popup UX) always binds the authorization
#: code to the special value ``postmessage`` instead of a real callback URL.
POSTMESSAGE_REDIRECT_URI = "postmessage"


class GoogleAuthError(Exception):
    """Raised when the Google exchange or profile fetch cannot complete."""


@dataclass(slots=True)
class GoogleUserProfile:
    """Normalized profile data returned by Google's userinfo endpoint."""

    google_id: str          # Google's "sub" claim — stable user identifier
    email: str
    full_name: str
    picture: str | None


class GoogleAuthService:
    """Thin wrapper around Google's token + userinfo endpoints."""

    def __init__(self, http_client: httpx.AsyncClient | None = None) -> None:
        self._http = http_client or httpx.AsyncClient(
            timeout=_GOOGLE_TIMEOUT_SECONDS, follow_redirects=True
        )

    async def aclose(self) -> None:
        """Release the underlying HTTP client (no-op for injected clients)."""
        await self._http.aclose()

    # ------------------------------------------------------------------
    # Step A: exchange the authorization code for Google tokens
    # ------------------------------------------------------------------
    async def exchange_code_for_tokens(
        self, code: str, redirect_uri: str | None = None
    ) -> dict[str, Any]:
        """Trade an authorization ``code`` for Google access/id tokens.

        Args:
            code: The one-time authorization code from the frontend.
            redirect_uri: The URI the code was issued against. Google requires
                an **exact** match with the value used at authorization time,
                otherwise the exchange fails with ``invalid_grant``. Popups
                bind codes to ``postmessage``; the redirect flow uses the
                configured ``GOOGLE_REDIRECT_URI``. ``None`` falls back to the
                configured value.

        Raises:
            GoogleAuthError: If Google rejects the code, the app is not
                configured, the redirect URI is not in the allowlist, or the
                request fails at the network level.
        """
        if not settings.GOOGLE_CLIENT_ID or not settings.GOOGLE_CLIENT_SECRET:
            raise GoogleAuthError(
                "Google OAuth is not configured on the server. "
                "Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET."
            )

        resolved_redirect_uri = _resolve_redirect_uri(redirect_uri)
        logger.info(
            "Google token exchange: code=…%s redirect_uri=%s",
            code[-6:] if code else "<empty>",
            resolved_redirect_uri,
        )

        data = {
            "code": code,
            "client_id": settings.GOOGLE_CLIENT_ID,
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
            "redirect_uri": resolved_redirect_uri,
            "grant_type": "authorization_code",
        }
        try:
            response = await self._http.post(GOOGLE_TOKEN_URL, data=data)
        except httpx.TimeoutException as exc:
            logger.exception("Google token exchange timed out")
            raise GoogleAuthError("Google sign-in timed out. Please try again.") from exc
        except httpx.HTTPError as exc:
            logger.exception("Google token exchange network failure")
            raise GoogleAuthError("Could not reach Google sign-in. Please try again.") from exc

        if response.status_code != 200:
            detail = _google_error_detail(response, "Google rejected the sign-in code.")
            logger.warning(
                "Google token exchange failed (status=%s body=%r)",
                response.status_code,
                response.text[:500],
            )
            raise GoogleAuthError(detail)

        body = response.json()
        logger.info("Google token exchange succeeded (token_type=%s)", body.get("token_type"))
        if not body.get("access_token"):
            raise GoogleAuthError("Google returned no access token for this code.")
        return body

    # ------------------------------------------------------------------
    # Step B: fetch the user's profile with the access token
    # ------------------------------------------------------------------
    async def fetch_user_info(self, access_token: str) -> dict[str, Any]:
        """Load email / name / picture / sub from Google's userinfo endpoint.

        Raises:
            GoogleAuthError: If the token is rejected or the request fails.
        """
        headers = {"Authorization": f"Bearer {access_token}"}
        try:
            response = await self._http.get(GOOGLE_USERINFO_URL, headers=headers)
        except httpx.TimeoutException as exc:
            raise GoogleAuthError("Google sign-in timed out. Please try again.") from exc
        except httpx.HTTPError as exc:
            raise GoogleAuthError("Could not reach Google sign-in. Please try again.") from exc

        if response.status_code != 200:
            detail = _google_error_detail(response, "Could not load your Google profile.")
            logger.warning("Google userinfo failed (status=%s)", response.status_code)
            raise GoogleAuthError(detail)

        user_info = response.json()
        logger.info("Google userinfo response: %s", user_info)
        return user_info

    # ------------------------------------------------------------------
    # Convenience: run both steps and normalize the profile
    # ------------------------------------------------------------------
    async def authenticate(
        self, code: str, redirect_uri: str | None = None
    ) -> GoogleUserProfile:
        """Exchange ``code`` and return a normalized :class:`GoogleUserProfile`.

        Args:
            code: The one-time authorization code from the frontend.
            redirect_uri: The URI the code was issued against (see
                :meth:`exchange_code_for_tokens`).

        Raises:
            GoogleAuthError: On any failure during the exchange/profile fetch.
        """
        tokens = await self.exchange_code_for_tokens(code, redirect_uri)
        info = await self.fetch_user_info(tokens["access_token"])

        google_id = info.get("sub")
        email = (info.get("email") or "").strip().lower()
        name = (info.get("name") or "").strip() or _default_name_from_email(email)
        picture = info.get("picture") or None

        if not google_id or not email:
            # Keep the complete payload in the server log for diagnosing
            # consent/scope issues. This is intentionally logged before the
            # generic client-facing error is raised.
            logger.warning(
                "Google userinfo missing required email or sub: %s", info
            )
            raise GoogleAuthError(
                "Google did not return enough profile data. "
                "Make sure the requested scopes include openid and email."
            )
        return GoogleUserProfile(
            google_id=google_id,
            email=email,
            full_name=name,
            picture=picture,
        )


def _resolve_redirect_uri(redirect_uri: str | None) -> str:
    """Pick the redirect URI for the token exchange from a strict allowlist.

    Google binds an authorization code to the ``redirect_uri`` used at
    authorization time and requires the *exact same value* during the
    exchange. Two values are legitimate here:

    * ``postmessage`` — codes issued by Google's JS popup flow
      (``useGoogleLogin`` default; ``redirect_uri`` is ignored there).
    * The configured ``GOOGLE_REDIRECT_URI`` — codes issued by the
      full-page redirect flow (``/oauth/callback``).

    Anything else is rejected, so a crafted client cannot make the server
    dance with arbitrary redirect URIs.
    """
    if redirect_uri is None or not redirect_uri.strip():
        return settings.GOOGLE_REDIRECT_URI
    candidate = redirect_uri.strip()
    allowed = {POSTMESSAGE_REDIRECT_URI, settings.GOOGLE_REDIRECT_URI.strip()}
    if candidate not in allowed:
        raise GoogleAuthError(
            "Unrecognized redirect URI for the Google sign-in flow. "
            "Update the frontend/backend GOOGLE_REDIRECT_URI configuration."
        )
    return candidate


def _default_name_from_email(email: str) -> str:
    """Derive a display name from the local part of an email address."""
    local = email.split("@", 1)[0].replace(".", " ").strip()
    return local.capitalize() if local else "Google user"


def _google_error_detail(response: httpx.Response, fallback: str) -> str:
    """Extract Google's ``error_description`` when the body carries one."""
    try:
        body = response.json()
        description = (body or {}).get("error_description")
    except ValueError:
        description = None
    return description or fallback


async def authenticate_with_google(
    code: str, redirect_uri: str | None = None
) -> GoogleUserProfile:
    """Module-level helper: swap a code for a profile with a self-managed client.

    Args:
        code: The one-time authorization code from the frontend.
        redirect_uri: The URI the code was issued against (allowlist-checked;
            see :func:`_resolve_redirect_uri`).

    Raises:
        GoogleAuthError: On any failure during the exchange/profile fetch.
    """
    service = GoogleAuthService()
    try:
        return await service.authenticate(code, redirect_uri)
    finally:
        await service.aclose()
