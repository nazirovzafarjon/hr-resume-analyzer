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
import pytest

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


class TestSendVerificationCodeEmail:
    """Outbound request shape, response parsing and error handling for 6-digit codes."""

    CODE = "849201"

    def test_posts_expected_payload_and_records_message_id(self, monkeypatch):
        captured: dict = {}

        class FakeResponse:
            status_code = 200
            content = b'{"id":"msg_verif_123"}'
            text = '{"id":"msg_verif_123"}'

            def json(self):
                return {"id": "msg_verif_123"}

        def fake_post(url, **kwargs):
            captured["url"] = url
            captured.update(kwargs)
            return FakeResponse()

        monkeypatch.setattr(settings, "RESEND_API_KEY", "re_test_secret")
        monkeypatch.setattr(settings, "EMAIL_FROM", "onboarding@resend.dev")
        monkeypatch.setattr(email_service.httpx, "post", fake_post)

        result = email_service.send_verification_code_email(EMAIL, self.CODE)
        assert result.success is True
        assert bool(result) is True
        assert result.message_id == "msg_verif_123"

        assert captured["url"] == email_service.RESEND_API_URL
        assert captured["headers"] == {"Authorization": "Bearer re_test_secret"}
        payload = captured["json"]
        assert payload["from"] == "onboarding@resend.dev"
        assert payload["to"] == [EMAIL]
        assert payload["subject"] == "Verify Your Email — Resume Analyzer"
        assert self.CODE in payload["html"]
        assert self.CODE in payload["text"]
        assert "expires in" in payload["text"]

    def test_does_not_call_network_without_api_key(self, monkeypatch):
        def must_not_be_called(*args, **kwargs):
            raise AssertionError("httpx.post must not run without an API key")

        monkeypatch.setattr(settings, "RESEND_API_KEY", "")
        monkeypatch.setattr(email_service.httpx, "post", must_not_be_called)

        result = email_service.send_verification_code_email(EMAIL, self.CODE)
        assert result.success is False
        assert bool(result) is False
        assert "missing" in result.error.lower()

    def test_sandbox_restriction_generates_actionable_error(self, monkeypatch):
        class FakeResponse:
            status_code = 403
            content = b'{"statusCode":403,"message":"You can only send testing emails to your own email address. To send to other domains, you must verify a domain at resend.com/domains","name":"validation_error"}'
            text = '{"statusCode":403,"message":"You can only send testing emails to your own email address. To send to other domains, you must verify a domain at resend.com/domains","name":"validation_error"}'

            def json(self):
                return {"message": "You can only send testing emails to your own email address."}

        monkeypatch.setattr(settings, "RESEND_API_KEY", "re_test_secret")
        monkeypatch.setattr(settings, "EMAIL_FROM", "onboarding@resend.dev")
        monkeypatch.setattr(email_service.httpx, "post", lambda *a, **k: FakeResponse())

        result = email_service.send_verification_code_email(EMAIL, self.CODE)
        assert result.success is False
        assert bool(result) is False
        assert "sandbox" in result.error.lower() or "verify a custom domain" in result.error.lower()

    def test_general_provider_error_handled_safely(self, monkeypatch):
        class FakeResponse:
            status_code = 500
            content = b'{"message":"Internal Server Error"}'
            text = '{"message":"Internal Server Error"}'

            def json(self):
                return {"message": "Internal Server Error"}

        monkeypatch.setattr(settings, "RESEND_API_KEY", "re_test_secret")
        monkeypatch.setattr(email_service.httpx, "post", lambda *a, **k: FakeResponse())

        result = email_service.send_verification_code_email(EMAIL, self.CODE)
        assert result.success is False
        assert bool(result) is False
        assert result.status_code == 500

    def test_network_failure_handled(self, monkeypatch):
        def boom(*args, **kwargs):
            raise httpx.ConnectError("connection refused")

        monkeypatch.setattr(settings, "RESEND_API_KEY", "re_test_secret")
        monkeypatch.setattr(email_service.httpx, "post", boom)

        result = email_service.send_verification_code_email(EMAIL, self.CODE)
        assert result.success is False
        assert bool(result) is False
        assert "unable to connect" in result.error.lower()


def _ok_response(kwargs, captured):
    captured.update(kwargs)
    response = httpx.Response(200, json={"id": "email_abc123"}, request=httpx.Request("POST", email_service.RESEND_API_URL))
    return response


class _FakeProviderResponse:
    """Minimal stand-in for an httpx.Response returned by the Resend API."""

    def __init__(self, status_code: int, text: str, json_data=None) -> None:
        self.status_code = status_code
        self.text = text
        self.content = text.encode("utf-8")
        self._json = json_data
        self.request = httpx.Request("POST", email_service.RESEND_API_URL)

    def json(self):
        if self._json is None:
            raise ValueError("no JSON body")
        return self._json


SANDBOX_BODY = (
    '{"statusCode":403,"message":"You can only send testing emails to your own '
    'email address (account.owner@resend-sandbox.example). To send emails to '
    'other recipients, please verify a domain at resend.com/domains",'
    '"name":"validation_error"}'
)


class TestResendRetryPolicy:
    """Only transient failures are retried; permanent 4xx fail immediately."""

    CODE = "135790"

    def _configure(self, monkeypatch) -> None:
        monkeypatch.setattr(settings, "RESEND_API_KEY", "re_test_secret")
        monkeypatch.setattr(settings, "EMAIL_FROM", "onboarding@resend.dev")
        # No real sleeping regardless of the ambient config.
        monkeypatch.setattr(email_service, "_sleep_backoff", lambda attempt: None)
        # DEBUG builds give the "app" logger its own handler and stop
        # propagation; restore it so caplog can observe the records.
        import logging

        monkeypatch.setattr(logging.getLogger("app"), "propagate", True)

    @pytest.mark.parametrize("status_code", [429, 500, 502, 503, 504])
    def test_transient_status_is_retried_then_succeeds(self, monkeypatch, status_code):
        self._configure(monkeypatch)
        calls: list[int] = []

        def fake_post(url, **kwargs):
            calls.append(status_code)
            if len(calls) == 1:
                return _FakeProviderResponse(status_code, "temporary", {"message": "later"})
            return _FakeProviderResponse(200, '{"id":"msg_after_retry"}', {"id": "msg_after_retry"})

        monkeypatch.setattr(email_service.httpx, "post", fake_post)

        result = email_service.send_verification_code_email(EMAIL, self.CODE)

        assert result.success is True
        assert result.message_id == "msg_after_retry"
        assert len(calls) == 2

    def test_transient_failure_gives_up_after_the_retry_budget(self, monkeypatch):
        self._configure(monkeypatch)
        calls: list[int] = []

        def fake_post(url, **kwargs):
            calls.append(1)
            return _FakeProviderResponse(503, "down", {"message": "down"})

        monkeypatch.setattr(email_service.httpx, "post", fake_post)

        result = email_service.send_verification_code_email(EMAIL, self.CODE)

        assert result.success is False
        assert result.status_code == 503
        assert len(calls) == settings.EMAIL_MAX_RETRIES + 1

    def test_permanent_403_is_never_retried(self, monkeypatch):
        self._configure(monkeypatch)
        calls: list[int] = []

        def fake_post(url, **kwargs):
            calls.append(1)
            return _FakeProviderResponse(403, SANDBOX_BODY)

        monkeypatch.setattr(email_service.httpx, "post", fake_post)

        result = email_service.send_verification_code_email(EMAIL, self.CODE)

        assert result.success is False
        assert result.status_code == 403
        assert "sandbox" in result.error.lower() or "verify a custom domain" in result.error.lower()
        assert len(calls) == 1  # a 403 can never succeed: retry would be pointless

    def test_read_timeout_fails_fast(self, monkeypatch):
        self._configure(monkeypatch)
        calls: list[int] = []

        def fake_post(url, **kwargs):
            calls.append(1)
            raise httpx.ReadTimeout("timed out")

        monkeypatch.setattr(email_service.httpx, "post", fake_post)

        result = email_service.send_verification_code_email(EMAIL, self.CODE)

        assert result.success is False
        assert "respond in time" in result.error
        assert len(calls) == 1

    def test_network_error_is_retried_then_reported(self, monkeypatch):
        self._configure(monkeypatch)
        calls: list[int] = []

        def fake_post(url, **kwargs):
            calls.append(1)
            raise httpx.ConnectError("connection refused")

        monkeypatch.setattr(email_service.httpx, "post", fake_post)

        result = email_service.send_verification_code_email(EMAIL, self.CODE)

        assert result.success is False
        assert "unable to connect" in result.error.lower()
        assert len(calls) == settings.EMAIL_MAX_RETRIES + 1

    def test_provider_error_log_is_sanitized(self, monkeypatch, caplog):
        import logging

        self._configure(monkeypatch)
        monkeypatch.setattr(
            email_service.httpx, "post", lambda *a, **k: _FakeProviderResponse(403, SANDBOX_BODY)
        )

        with caplog.at_level(logging.DEBUG):
            email_service.send_verification_code_email(EMAIL, self.CODE)

        # The provider body's address(es) and the recipient are never logged
        # verbatim, and the API key never reaches the log at all.
        assert "account.owner@resend-sandbox.example" not in caplog.text
        assert EMAIL not in caplog.text
        assert "re_test_secret" not in caplog.text
        assert "<redacted-email>" in caplog.text


class TestSenderConfiguration:
    """From/Reply-To/timeout are built from settings, never hardcoded."""

    CODE = "246810"

    def _capture(self, monkeypatch) -> dict:
        captured: dict = {}

        def fake_post(url, **kwargs):
            captured.update(kwargs)
            return _FakeProviderResponse(200, '{"id":"msg_ok"}', {"id": "msg_ok"})

        monkeypatch.setattr(settings, "RESEND_API_KEY", "re_test_secret")
        monkeypatch.setattr(email_service.httpx, "post", fake_post)
        return captured

    def test_display_name_renders_rfc5322_without_reply_to(self, monkeypatch):
        monkeypatch.setattr(settings, "EMAIL_FROM", "noreply@edubaselearning.uz")
        monkeypatch.setattr(settings, "EMAIL_FROM_NAME", "EduBase")
        monkeypatch.setattr(settings, "EMAIL_REPLY_TO", "")
        captured = self._capture(monkeypatch)

        email_service.send_verification_code_email(EMAIL, self.CODE)

        assert captured["json"]["from"] == "EduBase <noreply@edubaselearning.uz>"
        assert "reply_to" not in captured["json"]

    def test_reply_to_is_included_only_when_configured(self, monkeypatch):
        monkeypatch.setattr(settings, "EMAIL_FROM", "noreply@edubaselearning.uz")
        monkeypatch.setattr(settings, "EMAIL_FROM_NAME", "")
        monkeypatch.setattr(settings, "EMAIL_REPLY_TO", "support@edubaselearning.uz")
        captured = self._capture(monkeypatch)

        email_service.send_verification_code_email(EMAIL, self.CODE)

        assert captured["json"]["from"] == "noreply@edubaselearning.uz"
        assert captured["json"]["reply_to"] == "support@edubaselearning.uz"

    def test_existing_display_name_is_not_double_wrapped(self, monkeypatch):
        monkeypatch.setattr(settings, "EMAIL_FROM", "EduBase <noreply@edubaselearning.uz>")
        monkeypatch.setattr(settings, "EMAIL_FROM_NAME", "Ignored")
        monkeypatch.setattr(settings, "EMAIL_REPLY_TO", "")
        captured = self._capture(monkeypatch)

        email_service.send_verification_code_email(EMAIL, self.CODE)

        assert captured["json"]["from"] == "EduBase <noreply@edubaselearning.uz>"

    def test_request_timeout_comes_from_config(self, monkeypatch):
        monkeypatch.setattr(settings, "EMAIL_FROM", "noreply@edubaselearning.uz")
        monkeypatch.setattr(settings, "EMAIL_FROM_NAME", "")
        monkeypatch.setattr(settings, "EMAIL_REPLY_TO", "")
        monkeypatch.setattr(settings, "EMAIL_REQUEST_TIMEOUT", 7)
        captured = self._capture(monkeypatch)

        email_service.send_verification_code_email(EMAIL, self.CODE)

        assert captured["timeout"] == 7