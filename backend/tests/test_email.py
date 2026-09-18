"""Unit tests for the Resend mailer (:mod:`app.services.email`).

Covers the exact contract the auth service relies on:

* ``send_reset_password_email`` builds the payload the Resend REST API expects:
  ``from`` the configured sender, ``to`` the user, subject ``Reset Your Password``
  and an HTML/text body containing the one-click reset link.
* Without ``RESEND_API_KEY`` the function must *not* call the network: it logs
  the link and returns ``False`` so callers fall back to the console link.
* Request failures and HTTP error statuses from Resend are logged — never
  raised — and reported as ``False``.

``httpx.post`` is monkeypatched on the ``app.services.email.httpx`` module
reference, so these tests exercise the real code path without network access.
"""

import httpx

from app.core.config import settings
from app.services import email as email_service

EMAIL = "hr@example.com"
TOKEN = "reset-token-abc123"


class TestBuildResetLink:
    """The URL a recipient clicks; must stay URL-encoded and absolute."""

    def test_embeds_the_token_against_the_frontend_origin(self, monkeypatch):
        monkeypatch.setattr(settings, "FRONTEND_BASE_URL", "http://localhost:5173/")
        assert (
            email_service.build_reset_link(TOKEN)
            == f"http://localhost:5173/reset-password?token={TOKEN}"
        )

    def test_url_encodes_special_characters(self, monkeypatch):
        monkeypatch.setattr(settings, "FRONTEND_BASE_URL", "http://localhost:5173")
        link = email_service.build_reset_link("a b/c+d?e=f")
        assert "token=a%20b%2Fc%2Bd%3Fe%3Df" in link


class TestSendResetPasswordEmail:
    """Outbound request shape, fallbacks and failure handling."""

    def test_posts_the_expected_payload_and_reports_success(self, monkeypatch):
        captured: dict = {}

        class FakeResponse:
            status_code = 200
            content = b'{"id":"email_abc123"}'
            text = '{"id":"email_abc123"}'

            def json(self):
                return {"id": "email_abc123"}

        def fake_post(url, **kwargs):
            captured["url"] = url
            captured.update(kwargs)
            return FakeResponse()

        monkeypatch.setattr(settings, "RESEND_API_KEY", "re_test_secret")
        monkeypatch.setattr(settings, "EMAIL_FROM", "onboarding@resend.dev")
        monkeypatch.setattr(settings, "FRONTEND_BASE_URL", "http://localhost:5173")
        monkeypatch.setattr(email_service.httpx, "post", fake_post)

        assert email_service.send_reset_password_email(EMAIL, TOKEN) is True

        assert captured["url"] == email_service.RESEND_API_URL
        assert captured["headers"] == {"Authorization": "Bearer re_test_secret"}
        payload = captured["json"]
        assert payload["from"] == "onboarding@resend.dev"
        assert payload["to"] == [EMAIL]
        assert payload["subject"] == "Reset Your Password"
        assert f"http://localhost:5173/reset-password?token={TOKEN}" in payload["html"]
        assert f"http://localhost:5173/reset-password?token={TOKEN}" in payload["text"]

    def test_html_escapes_the_embedded_link(self, monkeypatch):
        captured: dict = {}
        monkeypatch.setattr(settings, "RESEND_API_KEY", "re_test_secret")
        monkeypatch.setattr(settings, "FRONTEND_BASE_URL", "http://localhost:5173")
        monkeypatch.setattr(email_service.httpx, "post", lambda *a, **k: _ok_response(k, captured))

        # build_reset_link() percent-encodes hostile token characters first...
        email_service.send_reset_password_email(EMAIL, "a&b<c>")
        html_body = captured["json"]["html"]
        assert "token=a%26b%3Cc%3E" in html_body
        assert "<script>" not in html_body

        # ...and html.escape() additionally neutralises special chars that the
        # FRONTEND_BASE_URL itself may carry (defence in depth).
        monkeypatch.setattr(settings, "FRONTEND_BASE_URL", "http://localhost:5173?a=1&b=2")
        email_service.send_reset_password_email(EMAIL, TOKEN)
        html_body = captured["json"]["html"]
        assert "?a=1&amp;b=2" in html_body

    def test_does_not_call_network_without_an_api_key(self, monkeypatch):
        def must_not_be_called(*args, **kwargs):
            raise AssertionError("httpx.post must not run without an API key")

        monkeypatch.setattr(settings, "RESEND_API_KEY", "")
        monkeypatch.setattr(email_service.httpx, "post", must_not_be_called)

        assert email_service.send_reset_password_email(EMAIL, TOKEN) is False

    def test_returns_false_when_resend_rejects_the_email(self, monkeypatch):
        class FakeResponse:
            status_code = 422
            content = b'{"name":"validation_error"}'
            text = '{"name":"validation_error"}'

            def json(self):
                raise AssertionError("error body is logged as text, never parsed")

        monkeypatch.setattr(settings, "RESEND_API_KEY", "re_test_secret")
        monkeypatch.setattr(
            email_service.httpx, "post", lambda *a, **k: FakeResponse()
        )

        assert email_service.send_reset_password_email(EMAIL, TOKEN) is False

    def test_returns_false_when_the_request_raises(self, monkeypatch):
        def boom(*args, **kwargs):
            raise httpx.ConnectError("connection refused")

        monkeypatch.setattr(settings, "RESEND_API_KEY", "re_test_secret")
        monkeypatch.setattr(email_service.httpx, "post", boom)

        assert email_service.send_reset_password_email(EMAIL, TOKEN) is False


def _ok_response(kwargs, captured):
    captured.update(kwargs)
    response = httpx.Response(200, json={"id": "email_abc123"}, request=httpx.Request("POST", email_service.RESEND_API_URL))
    return response