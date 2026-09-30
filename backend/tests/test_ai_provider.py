"""Settings -> "Connect your provider and API key", and provider resolution."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.config import settings
from app.core.encryption import decrypt_secret
from app.models.ai_provider_config import UserAIProviderConfig
from app.schemas.application_analysis import ApplicationAnalysis
from app.services import ai_provider as service
from app.services.ai.job_analyzer import AIProviderAuthError, AIServiceError
from tests.test_auto_analyze_filters import ANALYSIS

URL = "/api/auth/me/ai-provider"
SECRET = "sk-or-v1-supersecretkey-4f2a"
MODEL = "deepseek/deepseek-v4.1-flash"


def _save(client, headers, **overrides):
    body = {"provider": "openrouter", "model_id": MODEL, "api_key": SECRET, **overrides}
    return client.put(URL, json=body, headers=headers)


def _row(db_session, user_id) -> UserAIProviderConfig | None:
    db_session.expire_all()
    return (
        db_session.query(UserAIProviderConfig)
        .filter(UserAIProviderConfig.user_id == user_id)
        .one_or_none()
    )


class TestSettingsEndpoints:
    def test_default_state(self, client, user):
        body = client.get(URL, headers=user["headers"]).json()

        assert body["configured"] is False
        assert body["source"] == "default"
        assert body["provider"] is None and body["masked_api_key"] is None
        assert body["can_save"] is True
        assert set(body["supported_providers"]) == {"openrouter", "groq", "gemini"}

    def test_save_returns_metadata_but_never_the_key(self, client, user):
        response = _save(client, user["headers"])

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["configured"] is True
        assert body["source"] == "custom"
        assert body["provider"] == "openrouter"
        assert body["model_id"] == MODEL
        assert body["masked_api_key"] == "••••••••4f2a"
        assert "api_key" not in body
        assert SECRET not in response.text
        assert SECRET not in client.get(URL, headers=user["headers"]).text

    def test_key_is_encrypted_at_rest(self, client, user, db_session):
        _save(client, user["headers"])

        row = _row(db_session, user["id"])
        assert row.api_key_encrypted != SECRET
        assert SECRET not in row.api_key_encrypted
        assert decrypt_secret(row.api_key_encrypted) == SECRET
        assert row.api_key_last4 == "4f2a"

    def test_update_model_keeps_the_saved_key(self, client, user, db_session):
        _save(client, user["headers"])
        encrypted_before = _row(db_session, user["id"]).api_key_encrypted

        response = client.put(
            URL, json={"provider": "openrouter", "model_id": "openai/gpt-4o-mini"}, headers=user["headers"]
        )

        assert response.status_code == 200
        row = _row(db_session, user["id"])
        assert row.model_id == "openai/gpt-4o-mini"
        assert row.api_key_encrypted == encrypted_before

    def test_new_key_replaces_the_old_one(self, client, user, db_session):
        _save(client, user["headers"])
        _save(client, user["headers"], api_key="gsk_second-key-9999", provider="groq")

        row = _row(db_session, user["id"])
        assert row.provider == "groq"
        assert decrypt_secret(row.api_key_encrypted) == "gsk_second-key-9999"
        assert db_session.query(UserAIProviderConfig).count() == 1

    def test_key_required_for_first_save_and_provider_change(self, client, user):
        first = client.put(
            URL, json={"provider": "openrouter", "model_id": MODEL}, headers=user["headers"]
        )
        assert first.status_code == 422

        _save(client, user["headers"])
        switch = client.put(URL, json={"provider": "groq", "model_id": "llama"}, headers=user["headers"])
        assert switch.status_code == 422
        assert switch.json()["detail"] == "Enter the API key for this provider."

    @pytest.mark.parametrize(
        "overrides",
        [
            {"provider": "openai"},
            {"provider": ""},
            {"model_id": ""},
            {"model_id": "has spaces"},
            {"api_key": "short"},
            {"api_key": "sk key with spaces"},
            {"model_id": "m" * 201},
        ],
    )
    def test_invalid_input_is_rejected(self, client, user, db_session, overrides):
        response = _save(client, user["headers"], **overrides)

        assert response.status_code == 422
        assert _row(db_session, user["id"]) is None

    def test_delete_returns_to_the_default_provider(self, client, user, db_session):
        _save(client, user["headers"])

        body = client.delete(URL, headers=user["headers"]).json()

        assert body["configured"] is False and body["source"] == "default"
        assert _row(db_session, user["id"]) is None
        # Deleting again is harmless.
        assert client.delete(URL, headers=user["headers"]).status_code == 200

    def test_configurations_are_isolated_per_user(self, client, user, other_user, db_session):
        _save(client, user["headers"])

        other_view = client.get(URL, headers=other_user["headers"]).json()
        assert other_view["configured"] is False

        client.delete(URL, headers=other_user["headers"])
        assert _row(db_session, user["id"]) is not None

    def test_requires_authentication(self, client):
        assert client.get(URL).status_code == 401
        assert client.put(URL, json={}).status_code == 401
        assert client.delete(URL).status_code == 401
        assert client.post(f"{URL}/test", json={}).status_code == 401

    def test_saving_is_refused_without_a_server_encryption_key(
        self, client, user, db_session, monkeypatch
    ):
        monkeypatch.setattr(settings, "AI_CREDENTIAL_ENCRYPTION_KEY", "")

        assert client.get(URL, headers=user["headers"]).json()["can_save"] is False
        response = _save(client, user["headers"])
        assert response.status_code == 503
        assert _row(db_session, user["id"]) is None


class TestConnectionTest:
    def _test(self, client, headers, **overrides):
        body = {"provider": "openrouter", "model_id": MODEL, "api_key": SECRET, **overrides}
        return client.post(f"{URL}/test", json=body, headers=headers)

    def test_success(self, client, user, db_session):
        with patch.object(service, "_make_request_with_retry", new_callable=AsyncMock) as request:
            request.return_value = MagicMock(status_code=200)
            response = self._test(client, user["headers"])

        assert response.json() == {"ok": True, "message": "Connection successful."}
        kwargs = request.await_args.kwargs
        assert kwargs["headers"]["Authorization"] == f"Bearer {SECRET}"
        assert kwargs["json"]["model"] == MODEL
        assert kwargs["cfg"]["max_retries"] == 0
        # Testing never saves anything.
        assert _row(db_session, user["id"]) is None

    @pytest.mark.parametrize(
        ("error", "message"),
        [
            (AIProviderAuthError(), "The AI provider rejected the credentials."),
            (AIServiceError("not found", status_code=404), "The model ID was not accepted by the provider."),
            (AIServiceError("bad", status_code=400), "The model ID was not accepted by the provider."),
            (AIServiceError("down", status_code=503), "Unable to connect with the provided configuration."),
        ],
    )
    def test_failures_return_safe_messages(self, client, user, error, message):
        with patch.object(service, "_make_request_with_retry", new_callable=AsyncMock) as request:
            request.side_effect = error
            response = self._test(client, user["headers"])

        assert response.status_code == 200
        assert response.json() == {"ok": False, "message": message}
        assert SECRET not in response.text

    def test_uses_the_saved_key_when_none_is_entered(self, client, user):
        _save(client, user["headers"])
        with patch.object(service, "_make_request_with_retry", new_callable=AsyncMock) as request:
            request.return_value = MagicMock(status_code=200)
            response = client.post(
                f"{URL}/test", json={"provider": "openrouter", "model_id": MODEL}, headers=user["headers"]
            )

        assert response.json()["ok"] is True
        assert request.await_args.kwargs["headers"]["Authorization"] == f"Bearer {SECRET}"

    def test_needs_a_key_when_none_is_saved(self, client, user):
        response = client.post(
            f"{URL}/test", json={"provider": "openrouter", "model_id": MODEL}, headers=user["headers"]
        )
        assert response.status_code == 422


class TestResolution:
    def test_default_provider_when_nothing_is_configured(self, db_session, user):
        cfg = service.resolve_for_user(db_session, user["id"])

        expected = settings.ai_provider_config()
        assert cfg["source"] == "default"
        assert (cfg["provider"], cfg["model"], cfg["api_key"]) == (
            expected["provider"],
            expected["model"],
            expected["api_key"],
        )

    def test_custom_provider_when_configured(self, client, db_session, user):
        _save(client, user["headers"], provider="groq", model_id="llama-3.3-70b-versatile")

        cfg = service.resolve_for_user(db_session, user["id"])

        assert cfg["source"] == "custom"
        assert cfg["provider"] == "groq"
        assert cfg["api_key"] == SECRET
        assert cfg["model"] == "llama-3.3-70b-versatile"
        assert cfg["base_url"] == "https://api.groq.com/openai/v1"
        # Operational limits stay platform-controlled.
        assert cfg["max_retries"] == settings.AI_MAX_RETRIES

    def test_unreadable_key_raises_instead_of_falling_back(self, client, db_session, user):
        _save(client, user["headers"])
        row = _row(db_session, user["id"])
        row.api_key_encrypted = "not-a-valid-token"
        db_session.commit()

        with pytest.raises(AIServiceError) as excinfo:
            service.resolve_for_user(db_session, user["id"])
        assert excinfo.value.message == service.CUSTOM_KEY_UNREADABLE


class TestAnalysesUseTheOwnersProvider:
    def _analyze(self, client, worker, **mock_kwargs):
        with patch(
            "app.services.application_analysis.analyze_application", new_callable=AsyncMock, **mock_kwargs
        ) as analyze:
            response = client.post(f"/api/workers/{worker['id']}/analyze", headers=worker["headers"])
        return response, analyze

    def test_manual_analysis_uses_the_custom_key(self, client, sample_worker):
        _save(client, sample_worker["headers"])

        response, analyze = self._analyze(
            client, sample_worker, return_value=ApplicationAnalysis(**ANALYSIS)
        )

        assert response.status_code == 200
        cfg = analyze.await_args.kwargs["cfg"]
        assert (cfg["source"], cfg["api_key"], cfg["model"]) == ("custom", SECRET, MODEL)

    def test_manual_analysis_uses_the_default_without_custom(self, client, sample_worker):
        response, analyze = self._analyze(
            client, sample_worker, return_value=ApplicationAnalysis(**ANALYSIS)
        )

        assert response.status_code == 200
        assert analyze.await_args.kwargs["cfg"]["source"] == "default"

    def test_other_users_key_is_never_used(self, client, sample_worker, other_user):
        _save(client, other_user["headers"], api_key="sk-other-user-key-0000")

        _, analyze = self._analyze(client, sample_worker, return_value=ApplicationAnalysis(**ANALYSIS))

        assert analyze.await_args.kwargs["cfg"]["source"] == "default"

    def test_rejected_custom_key_fails_without_platform_fallback(self, client, sample_worker):
        _save(client, sample_worker["headers"])

        response, analyze = self._analyze(client, sample_worker, side_effect=AIProviderAuthError())

        assert analyze.await_count == 1
        body = response.json()
        assert body["analysis_status"] == "failed"
        assert body["analysis_error"] == service.CUSTOM_KEY_REJECTED

    def test_unreadable_custom_key_marks_the_analysis_failed(
        self, client, sample_worker, db_session, user
    ):
        _save(client, sample_worker["headers"])
        row = _row(db_session, user["id"])
        row.api_key_encrypted = "garbage"
        db_session.commit()

        response, analyze = self._analyze(client, sample_worker)

        assert analyze.await_count == 0
        assert response.json()["analysis_error"] == service.CUSTOM_KEY_UNREADABLE

    def test_job_vacancy_analysis_uses_the_custom_key(self, client, user):
        _save(client, user["headers"])
        with patch("app.routers.jobs.analyze_vacancy", new_callable=AsyncMock) as analyze:
            analyze.return_value = {
                "company_name": "Acme",
                "position": "Dev",
                "description": "",
                "required_skills": "",
                "required_experience": "",
            }
            response = client.post(
                "/api/jobs/analyze", json={"content": "Acme hires a dev"}, headers=user["headers"]
            )

        assert response.status_code == 200, response.text
        assert analyze.await_args.kwargs["cfg"]["api_key"] == SECRET

    def test_batch_analysis_uses_the_owners_custom_key(self, client, db_session, sample_worker, user):
        from app.models.user import User
        from app.services import auto_analyze

        _save(client, sample_worker["headers"])
        batch = auto_analyze.create_auto_analyze_batch(
            db_session, db_session.get(User, user["id"]), count=5
        )
        with patch(
            "app.services.application_analysis.analyze_application", new_callable=AsyncMock
        ) as analyze:
            analyze.return_value = ApplicationAnalysis(**ANALYSIS)
            asyncio.run(auto_analyze.run_batch_analysis(batch.id))

        assert analyze.await_args.kwargs["cfg"]["api_key"] == SECRET
