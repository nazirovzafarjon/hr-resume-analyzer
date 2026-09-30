"""An empty model answer (no text or ``{}``) is retried once, then explained."""

import json
import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.ai.application_analyzer import analyze_application
from app.services.ai.job_analyzer import (
    AIEmptyResponseError,
    AIInvalidResponseError,
    analyze_vacancy,
)
from tests.test_ai_rate_limit import (
    AI_ANALYSIS_RESPONSE,
    VACANCY_CONTENT,
    _FakeResponse,
    _make_cfg,
    _run,
)
from tests.test_auto_analyze_filters import ANALYSIS

FREE_MODEL = "qwen/qwen3.8-27b:free"


def _reply(content: str) -> _FakeResponse:
    return _FakeResponse(
        json_data={"choices": [{"message": {"content": content}, "finish_reason": "stop"}]}
    )


def _client(*replies: _FakeResponse) -> MagicMock:
    client = MagicMock()
    client.post = AsyncMock(side_effect=list(replies))
    return client


def _vacancy(client):
    with patch("app.services.ai.job_analyzer._get_client", return_value=client):
        return _run(analyze_vacancy(VACANCY_CONTENT, cfg=_make_cfg(model=FREE_MODEL)))


def _application(client):
    with patch("app.services.ai.application_analyzer._get_client", return_value=client):
        return _run(
            analyze_application(
                job_requirements="Python developer",
                form_answers="Name: Ann",
                resume_text="Python, FastAPI",
                cfg=_make_cfg(model=FREE_MODEL),
            )
        )


class TestEmptyAnswerIsRetriedOnce:
    @pytest.mark.parametrize("empty", ["{}", "```json\n{}\n```", "   "])
    def test_vacancy_analysis_recovers(self, empty):
        client = _client(_reply(empty), _reply(json.dumps(AI_ANALYSIS_RESPONSE)))

        result = _vacancy(client)

        assert result.company_name == "Acme Corp"
        assert client.post.await_count == 2

    def test_application_analysis_recovers(self):
        client = _client(_reply("{}"), _reply(json.dumps(ANALYSIS)))

        result = _application(client)

        assert result.match_percentage == ANALYSIS["match_percentage"]
        assert result.model == FREE_MODEL
        assert client.post.await_count == 2

    @pytest.mark.parametrize("run", [_vacancy, _application])
    def test_gives_up_after_the_retry_with_a_clear_message(self, run, caplog):
        client = _client(_reply("{}"), _reply("{}"), _reply(json.dumps(ANALYSIS)))

        with caplog.at_level(logging.WARNING), pytest.raises(AIEmptyResponseError) as exc:
            run(client)

        assert client.post.await_count == 2  # one retry, not more
        assert exc.value.status_code == 502
        assert f'"{FREE_MODEL}" returned an empty answer' in exc.value.message
        assert "Settings → AI provider" in exc.value.message
        assert f"model={FREE_MODEL}" in caplog.text


class TestOtherBadAnswersAreNotRetried:
    def test_missing_fields_fail_at_once(self):
        # Vacancy fields are all optional, so this only applies to applications.
        client = _client(_reply('{"unexpected": true}'), _reply(json.dumps(ANALYSIS)))

        with pytest.raises(AIInvalidResponseError) as exc:
            _application(client)

        assert not isinstance(exc.value, AIEmptyResponseError)
        assert client.post.await_count == 1

    def test_invalid_json_fails_at_once(self):
        client = _client(_reply("not json at all"), _reply(json.dumps(AI_ANALYSIS_RESPONSE)))

        with pytest.raises(AIInvalidResponseError) as exc:
            _vacancy(client)

        assert not isinstance(exc.value, AIEmptyResponseError)
        assert client.post.await_count == 1

    def test_validation_failures_log_the_model(self, caplog):
        client = _client(_reply('{"match_percentage": "lots"}'))

        with caplog.at_level(logging.ERROR), pytest.raises(AIInvalidResponseError):
            _application(client)

        assert f"model={FREE_MODEL}" in caplog.text


def test_the_message_reaches_the_hr(client, sample_application):
    """Manual analysis stores the explanation on the application."""
    with patch(
        "app.services.application_analysis.analyze_application",
        new_callable=AsyncMock,
        side_effect=AIEmptyResponseError(FREE_MODEL),
    ):
        response = client.post(
            f"/api/applications/{sample_application['id']}/analyze",
            headers=sample_application["headers"],
        )

    body = response.json()
    assert body["analysis_status"] == "failed"
    assert "returned an empty answer" in body["analysis_error"]
