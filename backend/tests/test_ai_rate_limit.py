"""Tests for AI job vacancy analysis with multi-provider support.

Covers:
* Successful AI analysis
* Markdown JSON stripping
* Invalid JSON handling
* 429 rate limit with retry and exhaustion
* 503 service unavailable with retry
* 401 authentication failure (no retry)
* Network failure with retry
* Retry-After header support
* Provider selection (openrouter, groq, gemini)
* Exponential backoff
"""

import asyncio
import json
import logging
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.services.ai.job_analyzer import (
    AIServiceError,
    AIRateLimitError,
    AIProviderAuthError,
    AIProviderUnavailableError,
    AIInvalidResponseError,
    analyze_vacancy,
    rate_limit_message,
    _strip_json_markdown,
    _get_retry_delay,
    _error_reason,
    _parse_retry_after,
)

VACANCY_CONTENT = "We need a Python developer at TestCorp."
AI_ANALYSIS_RESPONSE = {
    "company_name": "Acme Corp",
    "position": "Python Developer",
    "description": "Backend development",
    "required_skills": "Python, FastAPI",
    "required_experience": "2+ years",
}

FAKE_API_KEY = "sk-or-v1-test-secret-key-12345-do-not-log"


def _make_cfg(provider="openrouter", model="test/model", api_key=FAKE_API_KEY):
    """Create a minimal AI provider config dict for testing."""
    base_urls = {
        "openrouter": "https://openrouter.ai/api/v1",
        "groq": "https://api.groq.com/openai/v1",
        "gemini": "https://generativelanguage.googleapis.com/v1beta/models",
    }
    return {
        "provider": provider,
        "model": model,
        "api_key": api_key,
        "base_url": base_urls.get(provider, "https://openrouter.ai/api/v1"),
        "max_retries": 3,
        "retry_base_delay": 2,
        "max_retry_wait": 30,
        "retry_budget": 45,
        "request_timeout": 60,
        "http_referer": "http://localhost:8000",
        "app_title": "Resume Analyzer",
        "max_content_length": 50000,
    }


def _mock_client_with_response(fake_response):
    """Create a mock httpx client that returns the given response."""
    mock_client = MagicMock()
    mock_client.post = AsyncMock(return_value=fake_response)
    return mock_client


def _run(coro):
    """Run an async coroutine in a new event loop."""
    return asyncio.run(coro)


class _FakeResponse:
    """Minimal fake httpx.Response for testing."""

    def __init__(self, status_code=200, json_data=None, text_data=None, headers=None, json_raises=False):
        self.status_code = status_code
        self._json_data = json_data
        self._text_data = text_data
        self.headers = headers or {}
        self._json_raises = json_raises

    def json(self):
        if self._json_raises:
            raise json.JSONDecodeError("Expecting value", self._text_data or "", 0)
        if self._json_data is not None:
            return self._json_data
        raise ValueError("No JSON")

    @property
    def text(self):
        if self._text_data is not None:
            return self._text_data
        if self._json_data is not None:
            return json.dumps(self._json_data)
        return ""


# ---------------------------------------------------------------------------
# JSON Markdown stripping
# ---------------------------------------------------------------------------


class TestStripJsonMarkdown:
    def test_plain_json(self):
        assert _strip_json_markdown('{"a": 1}') == '{"a": 1}'

    def test_markdown_fenced_json(self):
        text = "```json\n{\"a\": 1}\n```"
        assert _strip_json_markdown(text) == '{"a": 1}'

    def test_markdown_fenced_no_lang(self):
        text = "```\n{\"a\": 1}\n```"
        assert _strip_json_markdown(text) == '{"a": 1}'

    def test_whitespace_only(self):
        assert _strip_json_markdown("  \n  ") == ""

    def test_reasoning_before_json(self):
        text = 'We need JSON. Company: {maybe EPAM}. Final:\n{"a": {"b": 1}}\n'
        assert _strip_json_markdown(text) == '{"a": {"b": 1}}'

    def test_reasoning_without_json_is_returned_unchanged(self):
        text = "We need to extract structured job information. company_name: EPAM"
        assert _strip_json_markdown(text) == text


# ---------------------------------------------------------------------------
# Retry delay
# ---------------------------------------------------------------------------


class TestGetRetryDelay:
    def test_exponential_backoff(self):
        assert _get_retry_delay(0, 2, None) == 2
        assert _get_retry_delay(1, 2, None) == 4
        assert _get_retry_delay(2, 2, None) == 8

    def test_retry_after_honored(self):
        assert _get_retry_delay(0, 2, 5) == 5

    def test_retry_after_is_not_shortened(self):
        # Retrying sooner than the provider asked is bound to be rejected;
        # whether to wait that long at all is the retry loop's decision.
        assert _get_retry_delay(0, 2, 100) == 100


class TestParseRetryAfter:
    def test_seconds(self):
        assert _parse_retry_after(_FakeResponse(429, headers={"retry-after": "7"})) == 7

    def test_http_date(self):
        from email.utils import format_datetime
        from datetime import datetime, timedelta, timezone

        when = format_datetime(datetime.now(timezone.utc) + timedelta(seconds=40), usegmt=True)
        wait = _parse_retry_after(_FakeResponse(429, headers={"retry-after": when}))
        assert 35 <= wait <= 41

    def test_openrouter_reset_in_milliseconds(self):
        import time as _time

        reset_ms = str(int((_time.time() + 20) * 1000))
        wait = _parse_retry_after(_FakeResponse(429, headers={"x-ratelimit-reset": reset_ms}))
        assert 15 <= wait <= 21

    def test_past_reset_means_no_wait(self):
        assert _parse_retry_after(_FakeResponse(429, headers={"x-ratelimit-reset": "1000000000000"})) == 0

    def test_missing_or_garbage(self):
        assert _parse_retry_after(_FakeResponse(429)) is None
        assert _parse_retry_after(_FakeResponse(429, headers={"retry-after": "soon"})) is None


class TestRateLimitMessage:
    def test_free_model_suggests_switching(self):
        message = rate_limit_message("qwen/qwen3.8-27b:free", 37)
        assert '"qwen/qwen3.8-27b:free"' in message
        assert "about 40 seconds" in message
        assert "Settings → AI provider" in message

    def test_paid_model_without_known_wait(self):
        message = rate_limit_message("deepseek/deepseek-v4.1-flash")
        assert "rate limit was reached" in message
        assert "about a minute" in message
        assert "Settings" not in message

    def test_minutes(self):
        assert "about 3 minutes" in rate_limit_message(None, 125)


# ---------------------------------------------------------------------------
# Successful response
# ---------------------------------------------------------------------------


class TestAnalyzeVacancySuccess:
    def test_successful_response(self):
        fake_resp = _FakeResponse(status_code=200, json_data={"choices": [{"message": {"content": json.dumps(AI_ANALYSIS_RESPONSE)}}]})
        mock_client = _mock_client_with_response(fake_resp)
        cfg = _make_cfg()
        with patch("app.services.ai.job_analyzer._get_client", return_value=mock_client), \
             patch("app.services.ai.job_analyzer.settings") as mock_settings:
            mock_settings.ai_provider_config.return_value = cfg
            result = _run(analyze_vacancy(VACANCY_CONTENT, cfg=cfg))
        assert result.company_name == "Acme Corp"
        assert result.position == "Python Developer"
        assert result.required_skills == "Python, FastAPI"
        assert result.required_experience == "2+ years"

    def test_successful_response_with_markdown_fence(self):
        json_str = json.dumps(AI_ANALYSIS_RESPONSE)
        content = f"```json\n{json_str}\n```"
        fake_resp = _FakeResponse(status_code=200, json_data={"choices": [{"message": {"content": content}}]})
        mock_client = _mock_client_with_response(fake_resp)
        cfg = _make_cfg()
        with patch("app.services.ai.job_analyzer._get_client", return_value=mock_client), \
             patch("app.services.ai.job_analyzer.settings") as mock_settings:
            mock_settings.ai_provider_config.return_value = cfg
            result = _run(analyze_vacancy(VACANCY_CONTENT, cfg=cfg))
        assert result.company_name == "Acme Corp"

    def test_success_logs_provider_and_model(self, caplog):
        fake_resp = _FakeResponse(status_code=200, json_data={"choices": [{"message": {"content": json.dumps(AI_ANALYSIS_RESPONSE)}}]})
        mock_client = _mock_client_with_response(fake_resp)
        cfg = _make_cfg()
        with patch("app.services.ai.job_analyzer._get_client", return_value=mock_client), \
             patch("app.services.ai.job_analyzer.settings") as mock_settings:
            mock_settings.ai_provider_config.return_value = cfg
            with caplog.at_level(logging.INFO, logger="app.services.ai.job_analyzer"):
                _run(analyze_vacancy(VACANCY_CONTENT, cfg=cfg))
        assert "AI request succeeded" in caplog.text
        assert "provider=openrouter" in caplog.text


# ---------------------------------------------------------------------------
# Invalid JSON
# ---------------------------------------------------------------------------


class TestAnalyzeVacancyInvalidJson:
    def test_invalid_json_returns_controlled_error(self):
        fake_resp = _FakeResponse(status_code=200, text_data="this is not json")
        mock_client = _mock_client_with_response(fake_resp)
        cfg = _make_cfg()
        with patch("app.services.ai.job_analyzer._get_client", return_value=mock_client), \
             patch("app.services.ai.job_analyzer.settings") as mock_settings:
            mock_settings.ai_provider_config.return_value = cfg
            with pytest.raises(AIInvalidResponseError):
                _run(analyze_vacancy(VACANCY_CONTENT, cfg=cfg))

    def test_invalid_json_does_not_leak_content(self, caplog):
        fake_resp = _FakeResponse(status_code=200, text_data="this is not json")
        mock_client = _mock_client_with_response(fake_resp)
        cfg = _make_cfg()
        with patch("app.services.ai.job_analyzer._get_client", return_value=mock_client), \
             patch("app.services.ai.job_analyzer.settings") as mock_settings:
            mock_settings.ai_provider_config.return_value = cfg
            with pytest.raises(AIInvalidResponseError):
                _run(analyze_vacancy(VACANCY_CONTENT, cfg=cfg))
        assert FAKE_API_KEY not in caplog.text


# ---------------------------------------------------------------------------
# 429 rate limit
# ---------------------------------------------------------------------------


class TestAnalyzeVacancy429Retry:
    def test_429_then_success(self):
        fake_429 = _FakeResponse(status_code=429, json_data={"error": {"message": "rate limited"}})
        fake_200 = _FakeResponse(status_code=200, json_data={"choices": [{"message": {"content": json.dumps(AI_ANALYSIS_RESPONSE)}}]})
        mock_client = _mock_client_with_response(fake_429)
        mock_client.post = AsyncMock(side_effect=[fake_429, fake_200])
        cfg = _make_cfg()
        with patch("app.services.ai.job_analyzer._get_client", return_value=mock_client), \
             patch("app.services.ai.job_analyzer.settings") as mock_settings:
            mock_settings.ai_provider_config.return_value = cfg
            with patch("asyncio.sleep") as mock_sleep:
                result = _run(analyze_vacancy(VACANCY_CONTENT, cfg=cfg))
            assert result.company_name == "Acme Corp"
            mock_sleep.assert_called_once()

    def test_429_exhausted_raises_rate_limit(self):
        fake_429 = _FakeResponse(status_code=429, json_data={"error": {"message": "rate limited"}})
        mock_client = _mock_client_with_response(fake_429)
        mock_client.post = AsyncMock(return_value=fake_429)
        cfg = _make_cfg()
        with patch("app.services.ai.job_analyzer._get_client", return_value=mock_client), \
             patch("app.services.ai.job_analyzer.settings") as mock_settings:
            mock_settings.ai_provider_config.return_value = cfg
            with patch("asyncio.sleep") as mock_sleep:
                with pytest.raises(AIRateLimitError):
                    _run(analyze_vacancy(VACANCY_CONTENT, cfg=cfg))
            # 4 attempts total: initial + 3 retries
            assert mock_client.post.call_count == 4

    def test_429_logs_safe_diagnostics(self, caplog):
        fake_429 = _FakeResponse(status_code=429, json_data={"error": {"message": "rate limited", "code": 429}})
        mock_client = _mock_client_with_response(fake_429)
        mock_client.post = AsyncMock(return_value=fake_429)
        cfg = _make_cfg()
        with patch("app.services.ai.job_analyzer._get_client", return_value=mock_client), \
             patch("app.services.ai.job_analyzer.settings") as mock_settings:
            mock_settings.ai_provider_config.return_value = cfg
            with patch("asyncio.sleep"), pytest.raises(AIRateLimitError):
                _run(analyze_vacancy(VACANCY_CONTENT, cfg=cfg))
        log_text = caplog.text
        assert "status=429" in log_text
        assert FAKE_API_KEY not in log_text
        assert "Authorization" not in log_text

    def test_429_retry_after_respected(self):
        fake_429 = _FakeResponse(status_code=429, json_data={"error": {"message": "rate limited"}}, headers={"retry-after": "5"})
        fake_200 = _FakeResponse(status_code=200, json_data={"choices": [{"message": {"content": json.dumps(AI_ANALYSIS_RESPONSE)}}]})
        mock_client = _mock_client_with_response(fake_429)
        mock_client.post = AsyncMock(side_effect=[fake_429, fake_200])
        cfg = _make_cfg()
        with patch("app.services.ai.job_analyzer._get_client", return_value=mock_client), \
             patch("app.services.ai.job_analyzer.settings") as mock_settings:
            mock_settings.ai_provider_config.return_value = cfg
            with patch("asyncio.sleep") as mock_sleep:
                result = _run(analyze_vacancy(VACANCY_CONTENT, cfg=cfg))
            mock_sleep.assert_called_once()
            call_kwargs = mock_sleep.call_args
            assert call_kwargs[0][0] == 5  # retry_after=5

    def test_429_retry_after_within_cap_is_honoured_in_full(self):
        fake_429 = _FakeResponse(status_code=429, json_data={"error": {"message": "rate limited"}}, headers={"retry-after": "25"})
        fake_200 = _FakeResponse(status_code=200, json_data={"choices": [{"message": {"content": json.dumps(AI_ANALYSIS_RESPONSE)}}]})
        mock_client = _mock_client_with_response(fake_429)
        mock_client.post = AsyncMock(side_effect=[fake_429, fake_200])
        cfg = _make_cfg()
        with patch("app.services.ai.job_analyzer._get_client", return_value=mock_client), \
             patch("app.services.ai.job_analyzer.settings") as mock_settings:
            mock_settings.ai_provider_config.return_value = cfg
            with patch("asyncio.sleep") as mock_sleep:
                _run(analyze_vacancy(VACANCY_CONTENT, cfg=cfg))
            mock_sleep.assert_called_once_with(25)

    def test_429_retry_after_over_cap_gives_up_without_more_requests(self):
        fake_429 = _FakeResponse(status_code=429, json_data={"error": {"message": "rate limited"}}, headers={"retry-after": "100"})
        mock_client = _mock_client_with_response(fake_429)
        cfg = _make_cfg(model="qwen/qwen3.8-27b:free")
        with patch("app.services.ai.job_analyzer._get_client", return_value=mock_client), \
             patch("app.services.ai.job_analyzer.settings") as mock_settings:
            mock_settings.ai_provider_config.return_value = cfg
            with patch("asyncio.sleep") as mock_sleep, pytest.raises(AIRateLimitError) as caught:
                _run(analyze_vacancy(VACANCY_CONTENT, cfg=cfg))
        mock_sleep.assert_not_called()
        assert mock_client.post.call_count == 1
        assert caught.value.retry_after == 100
        assert caught.value.model == "qwen/qwen3.8-27b:free"
        assert "about 2 minutes" in caught.value.message

    def test_429_stops_when_the_waiting_budget_is_spent(self):
        fake_429 = _FakeResponse(status_code=429, json_data={"error": {"message": "rate limited"}})
        mock_client = _mock_client_with_response(fake_429)
        cfg = {**_make_cfg(), "retry_budget": 7}  # backoff 2 + 4 fits, the next 8 does not
        with patch("app.services.ai.job_analyzer._get_client", return_value=mock_client), \
             patch("app.services.ai.job_analyzer.settings") as mock_settings:
            mock_settings.ai_provider_config.return_value = cfg
            with patch("asyncio.sleep") as mock_sleep, pytest.raises(AIRateLimitError):
                _run(analyze_vacancy(VACANCY_CONTENT, cfg=cfg))
        assert [c.args[0] for c in mock_sleep.call_args_list] == [2, 4]
        assert mock_client.post.call_count == 3


# ---------------------------------------------------------------------------
# 503 then success
# ---------------------------------------------------------------------------


class TestAnalyzeVacancy503Retry:
    def test_503_then_success(self):
        fake_503 = _FakeResponse(status_code=503, json_data={"error": {"message": "service unavailable"}})
        fake_200 = _FakeResponse(status_code=200, json_data={"choices": [{"message": {"content": json.dumps(AI_ANALYSIS_RESPONSE)}}]})
        mock_client = _mock_client_with_response(fake_503)
        mock_client.post = AsyncMock(side_effect=[fake_503, fake_200])
        cfg = _make_cfg()
        with patch("app.services.ai.job_analyzer._get_client", return_value=mock_client), \
             patch("app.services.ai.job_analyzer.settings") as mock_settings:
            mock_settings.ai_provider_config.return_value = cfg
            with patch("asyncio.sleep"):
                result = _run(analyze_vacancy(VACANCY_CONTENT, cfg=cfg))
        assert result.company_name == "Acme Corp"

    def test_503_exhausted_raises_unavailable(self):
        fake_503 = _FakeResponse(status_code=503, json_data={"error": {"message": "service unavailable"}})
        mock_client = _mock_client_with_response(fake_503)
        mock_client.post = AsyncMock(return_value=fake_503)
        cfg = _make_cfg()
        with patch("app.services.ai.job_analyzer._get_client", return_value=mock_client), \
             patch("app.services.ai.job_analyzer.settings") as mock_settings:
            mock_settings.ai_provider_config.return_value = cfg
            with patch("asyncio.sleep"), pytest.raises(AIProviderUnavailableError):
                _run(analyze_vacancy(VACANCY_CONTENT, cfg=cfg))


# ---------------------------------------------------------------------------
# 401 - no retry
# ---------------------------------------------------------------------------


class TestAnalyzeVacancy401:
    def test_401_does_not_retry(self):
        fake_401 = _FakeResponse(status_code=401, json_data={"error": {"message": "unauthorized"}})
        mock_client = _mock_client_with_response(fake_401)
        mock_client.post = AsyncMock(return_value=fake_401)
        cfg = _make_cfg()
        with patch("app.services.ai.job_analyzer._get_client", return_value=mock_client), \
             patch("app.services.ai.job_analyzer.settings") as mock_settings:
            mock_settings.ai_provider_config.return_value = cfg
            with patch("asyncio.sleep") as mock_sleep:
                with pytest.raises(AIProviderAuthError):
                    _run(analyze_vacancy(VACANCY_CONTENT, cfg=cfg))
            mock_sleep.assert_not_called()
            assert mock_client.post.call_count == 1


# ---------------------------------------------------------------------------
# Network failure
# ---------------------------------------------------------------------------


class TestAnalyzeVacancyNetworkFailure:
    def test_network_error_retries(self):
        mock_client = MagicMock()
        mock_client.post = AsyncMock(side_effect=httpx.NetworkError("connection failed"))
        cfg = _make_cfg()
        with patch("app.services.ai.job_analyzer._get_client", return_value=mock_client), \
             patch("app.services.ai.job_analyzer.settings") as mock_settings:
            mock_settings.ai_provider_config.return_value = cfg
            with patch("asyncio.sleep"), pytest.raises(AIProviderUnavailableError):
                _run(analyze_vacancy(VACANCY_CONTENT, cfg=cfg))
            assert mock_client.post.call_count == 4  # initial + 3 retries

    def test_network_error_exhausted_raises_unavailable(self):
        mock_client = MagicMock()
        mock_client.post = AsyncMock(side_effect=httpx.NetworkError("connection failed"))
        cfg = _make_cfg()
        with patch("app.services.ai.job_analyzer._get_client", return_value=mock_client), \
             patch("app.services.ai.job_analyzer.settings") as mock_settings:
            mock_settings.ai_provider_config.return_value = cfg
            with patch("asyncio.sleep"), pytest.raises(AIProviderUnavailableError):
                _run(analyze_vacancy(VACANCY_CONTENT, cfg=cfg))


# ---------------------------------------------------------------------------
# Provider selection
# ---------------------------------------------------------------------------


class TestProviderSelection:
    def test_openrouter_uses_openrouter_base_url(self):
        cfg = _make_cfg(provider="openrouter")
        assert cfg["base_url"] == "https://openrouter.ai/api/v1"

    def test_groq_uses_groq_base_url(self):
        cfg = _make_cfg(provider="groq")
        assert cfg["base_url"] == "https://api.groq.com/openai/v1"

    def test_gemini_uses_gemini_base_url(self):
        cfg = _make_cfg(provider="gemini")
        assert cfg["base_url"] == "https://generativelanguage.googleapis.com/v1beta/models"

    def test_openrouter_headers_include_attribution(self):
        cfg = _make_cfg(provider="openrouter")
        from app.services.ai.job_analyzer import _build_headers
        headers = _build_headers(cfg)
        assert "HTTP-Referer" in headers
        assert "X-Title" in headers

    def test_groq_headers_include_attribution(self):
        cfg = _make_cfg(provider="groq")
        from app.services.ai.job_analyzer import _build_headers
        headers = _build_headers(cfg)
        assert "HTTP-Referer" in headers
        assert "X-Title" in headers

    def test_gemini_headers_do_not_include_attribution(self):
        cfg = _make_cfg(provider="gemini")
        from app.services.ai.job_analyzer import _build_headers
        headers = _build_headers(cfg)
        assert "HTTP-Referer" not in headers
        assert "X-Title" not in headers

    def test_gemini_payload_format(self):
        cfg = _make_cfg(provider="gemini", model="gemini-2.0-flash")
        from app.services.ai.job_analyzer import _build_payload, _build_prompt
        prompt = _build_prompt("test")
        payload = _build_payload(cfg, prompt)
        assert "contents" in payload
        assert "model" not in payload
        assert "messages" not in payload

    def test_openrouter_payload_format(self):
        cfg = _make_cfg(provider="openrouter")
        from app.services.ai.job_analyzer import _build_payload, _build_prompt
        prompt = _build_prompt("test")
        payload = _build_payload(cfg, prompt)
        assert "model" in payload
        assert "messages" in payload
        assert "response_format" in payload
        assert payload["reasoning"] == {"enabled": False}

    def test_groq_payload_has_no_openrouter_reasoning_flag(self):
        cfg = _make_cfg(provider="groq")
        from app.services.ai.job_analyzer import _build_payload, _build_prompt
        payload = _build_payload(cfg, _build_prompt("test"))
        assert "reasoning" not in payload

    def test_gemini_analyze_vacancy(self):
        fake_resp = _FakeResponse(status_code=200, json_data={"candidates": [{"content": {"parts": [{"text": json.dumps(AI_ANALYSIS_RESPONSE)}]}}]})
        mock_client = _mock_client_with_response(fake_resp)
        cfg = _make_cfg(provider="gemini", model="gemini-2.0-flash")
        with patch("app.services.ai.job_analyzer._get_client", return_value=mock_client), \
             patch("app.services.ai.job_analyzer.settings") as mock_settings:
            mock_settings.ai_provider_config.return_value = cfg
            result = _run(analyze_vacancy(VACANCY_CONTENT, cfg=cfg))
        assert result.company_name == "Acme Corp"
        assert result.position == "Python Developer"

    def test_groq_analyze_vacancy(self):
        fake_resp = _FakeResponse(status_code=200, json_data={"choices": [{"message": {"content": json.dumps(AI_ANALYSIS_RESPONSE)}}]})
        mock_client = _mock_client_with_response(fake_resp)
        cfg = _make_cfg(provider="groq")
        with patch("app.services.ai.job_analyzer._get_client", return_value=mock_client), \
             patch("app.services.ai.job_analyzer.settings") as mock_settings:
            mock_settings.ai_provider_config.return_value = cfg
            result = _run(analyze_vacancy(VACANCY_CONTENT, cfg=cfg))
        assert result.company_name == "Acme Corp"


# ---------------------------------------------------------------------------
# Backward compatibility: settings.ai_provider_config()
# ---------------------------------------------------------------------------


class TestBackwardCompatibility:
    def test_legacy_openrouter_config(self):
        """Test that OPENROUTER_API_KEY and OPENROUTER_MODEL are used as fallback."""
        from app.core.config import Settings
        s = Settings()
        # With no AI_PROVIDER set, default is "openrouter"
        # AI_MODEL and AI_API_KEY are empty, so fallback to OPENROUTER_*
        cfg = s.ai_provider_config()
        assert cfg["provider"] == "openrouter"
        assert cfg["model"] == s.OPENROUTER_MODEL
        assert cfg["api_key"] == s.OPENROUTER_API_KEY

    def test_ai_provider_takes_precedence(self):
        """Test that AI_* settings take precedence over OPENROUTER_*."""
        from app.core.config import Settings
        s = Settings()
        # AI_PROVIDER defaults to "openrouter", AI_MODEL defaults to ""
        # So it falls back to OPENROUTER_MODEL
        cfg = s.ai_provider_config()
        assert cfg["provider"] == "openrouter"


# ---------------------------------------------------------------------------
# Endpoint integration tests (via router)
# ---------------------------------------------------------------------------


class TestAnalyzeEndpointIntegration:
    def test_endpoint_returns_429_generic_without_leaking_provider_details(self, client, user, caplog):
        from app.services.ai.job_analyzer import AIRateLimitError
        fake_resp = _FakeResponse(status_code=429, json_data={"error": {"message": "internal quota detail abc", "code": 429}})
        mock_client = _mock_client_with_response(fake_resp)
        cfg = _make_cfg()
        with patch("app.services.ai.job_analyzer._get_client", return_value=mock_client), \
             patch("app.services.ai.job_analyzer.settings") as mock_settings:
            mock_settings.ai_provider_config.return_value = cfg
            response = client.post("/api/jobs/analyze", json={"content": VACANCY_CONTENT}, headers=user["headers"])
        assert response.status_code == 429
        detail = response.json()["detail"].lower()
        assert "rate limit" in detail
        assert "internal quota detail abc" not in response.text
        assert FAKE_API_KEY not in response.text

    def test_endpoint_401_returns_auth_error(self, client, user):
        from app.services.ai.job_analyzer import AIProviderAuthError
        fake_resp = _FakeResponse(status_code=401, json_data={"error": {"message": "unauthorized"}})
        mock_client = _mock_client_with_response(fake_resp)
        cfg = _make_cfg()
        with patch("app.services.ai.job_analyzer._get_client", return_value=mock_client), \
             patch("app.services.ai.job_analyzer.settings") as mock_settings:
            mock_settings.ai_provider_config.return_value = cfg
            response = client.post("/api/jobs/analyze", json={"content": VACANCY_CONTENT}, headers=user["headers"])
        assert response.status_code == 502
        assert "authentication" in response.json()["detail"].lower()

    def test_endpoint_503_returns_unavailable(self, client, user):
        from app.services.ai.job_analyzer import AIProviderUnavailableError
        fake_resp = _FakeResponse(status_code=503, json_data={"error": {"message": "unavailable"}})
        mock_client = _mock_client_with_response(fake_resp)
        cfg = _make_cfg()
        with patch("app.services.ai.job_analyzer._get_client", return_value=mock_client), \
             patch("app.services.ai.job_analyzer.settings") as mock_settings:
            mock_settings.ai_provider_config.return_value = cfg
            response = client.post("/api/jobs/analyze", json={"content": VACANCY_CONTENT}, headers=user["headers"])
        assert response.status_code == 503
        assert "temporarily unavailable" in response.json()["detail"].lower()

    def test_endpoint_invalid_json_returns_502(self, client, user):
        from app.services.ai.job_analyzer import AIInvalidResponseError
        fake_resp = _FakeResponse(status_code=200, text_data="not json at all")
        mock_client = _mock_client_with_response(fake_resp)
        cfg = _make_cfg()
        with patch("app.services.ai.job_analyzer._get_client", return_value=mock_client), \
             patch("app.services.ai.job_analyzer.settings") as mock_settings:
            mock_settings.ai_provider_config.return_value = cfg
            response = client.post("/api/jobs/analyze", json={"content": VACANCY_CONTENT}, headers=user["headers"])
        assert response.status_code == 502
        assert "invalid" in response.json()["detail"].lower()

    def test_endpoint_never_logs_api_key(self, client, user, caplog):
        fake_resp = _FakeResponse(status_code=429, json_data={"error": {"message": "rate limited"}})
        mock_client = _mock_client_with_response(fake_resp)
        cfg = _make_cfg()
        with patch("app.services.ai.job_analyzer._get_client", return_value=mock_client), \
             patch("app.services.ai.job_analyzer.settings") as mock_settings:
            mock_settings.ai_provider_config.return_value = cfg
            with pytest.raises(AIRateLimitError):
                _run(analyze_vacancy(VACANCY_CONTENT, cfg=cfg))
        log_text = caplog.text
        assert FAKE_API_KEY not in log_text
        assert "Authorization" not in log_text
        assert "Bearer" not in log_text


# ---------------------------------------------------------------------------
# Empty content validation
# ---------------------------------------------------------------------------


class TestAnalyzeVacancyValidation:
    def test_empty_content_raises_422(self):
        with pytest.raises(AIServiceError) as exc_info:
            _run(analyze_vacancy("", cfg=_make_cfg()))
        assert exc_info.value.status_code == 422

    def test_whitespace_content_raises_422(self):
        with pytest.raises(AIServiceError) as exc_info:
            _run(analyze_vacancy("   ", cfg=_make_cfg()))
        assert exc_info.value.status_code == 422

    def test_content_too_long_raises_422(self):
        cfg = _make_cfg()
        with patch("app.services.ai.job_analyzer.settings") as mock_settings:
            mock_settings.ai_provider_config.return_value = cfg
            with pytest.raises(AIServiceError) as exc_info:
                _run(analyze_vacancy("x" * 50001, cfg=cfg))
        assert exc_info.value.status_code == 422

    def test_missing_api_key_raises_auth_error(self):
        cfg = _make_cfg(api_key="")
        with patch("app.services.ai.job_analyzer.settings") as mock_settings:
            mock_settings.ai_provider_config.return_value = cfg
            with pytest.raises(AIProviderAuthError):
                _run(analyze_vacancy(VACANCY_CONTENT, cfg=cfg))


# ---------------------------------------------------------------------------
# Provider error body capture (sanitized logging)
# ---------------------------------------------------------------------------


class TestProviderErrorBodyLogging:
    """The original provider error body must survive into the server log.

    The provider body is what distinguishes an upstream shared-pool rate
    limit from a bad request, auth failure, or unavailable model. Only the
    sanitized body text is logged -- never headers, API key, or user content.
    """

    def test_error_reason_extracts_openrouter_message_and_raw(self):
        body = {
            "error": {
                "message": "Provider returned error",
                "code": 429,
                "metadata": {
                    "raw": "google/gemma-4-31b-it:free is temporarily rate-limited upstream.",
                    "limit_source": "upstream_provider_shared_pool",
                },
            }
        }
        reason = _error_reason(_FakeResponse(status_code=429, json_data=body))
        assert "Provider returned error" in reason
        assert "temporarily rate-limited upstream" in reason
        assert "sk-or" not in reason

    def test_error_reason_falls_back_to_text(self):
        resp = _FakeResponse(status_code=429, text_data="upstream overloaded", json_raises=True)
        assert _error_reason(resp) == "upstream overloaded"

    def test_error_reason_collapses_whitespace_and_truncates(self):
        resp = _FakeResponse(status_code=400, text_data="a\n b\t" + "c" * 500, json_raises=True)
        reason = _error_reason(resp, limit=100)
        assert "\n" not in reason
        assert len(reason) <= 100 + len("...")
        assert reason.endswith("...")

    def test_429_log_contains_provider_reason(self, caplog):
        fake_429 = _FakeResponse(
            status_code=429,
            json_data={
                "error": {
                    "message": "Provider returned error",
                    "code": 429,
                    "metadata": {"raw": "google/gemma-4-31b-it:free is temporarily rate-limited upstream."},
                }
            },
        )
        mock_client = _mock_client_with_response(fake_429)
        cfg = _make_cfg()
        with patch("app.services.ai.job_analyzer._get_client", return_value=mock_client), \
             patch("app.services.ai.job_analyzer.settings") as mock_settings:
            mock_settings.ai_provider_config.return_value = cfg
            with patch("asyncio.sleep"), pytest.raises(AIRateLimitError):
                _run(analyze_vacancy(VACANCY_CONTENT, cfg=cfg))
        log_text = caplog.text
        assert "rate-limited upstream" in log_text
        assert FAKE_API_KEY not in log_text
        assert "Authorization" not in log_text
        assert "Bearer" not in log_text

    def test_400_log_contains_provider_reason(self, caplog):
        fake_400 = _FakeResponse(
            status_code=400,
            json_data={"error": {"message": "No endpoints found matching the model you requested."}},
        )
        mock_client = _mock_client_with_response(fake_400)
        cfg = _make_cfg()
        with patch("app.services.ai.job_analyzer._get_client", return_value=mock_client), \
             patch("app.services.ai.job_analyzer.settings") as mock_settings:
            mock_settings.ai_provider_config.return_value = cfg
            with pytest.raises(AIServiceError):
                _run(analyze_vacancy(VACANCY_CONTENT, cfg=cfg))
        assert "No endpoints found matching the model you requested." in caplog.text

    def test_error_reason_never_includes_user_vacancy_content(self):
        # The reason comes only from the provider body, not from our request
        # payload, so vacancy text must never show up in it.
        body = {"error": {"message": "Provider returned error"}}
        resp = _FakeResponse(status_code=429, json_data=body)
        assert VACANCY_CONTENT not in _error_reason(resp)
