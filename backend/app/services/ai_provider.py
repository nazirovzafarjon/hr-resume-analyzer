"""Which AI provider, key and model an HR user's AI operations use.

Resolution rule (the single place it lives):

1. The user has an active custom configuration (Settings -> "Connect your
   provider and API key") -> their provider, their decrypted key, their model.
2. Otherwise -> the platform provider from the environment
   (``settings.ai_provider_config()``), exactly as before.

A broken custom configuration (for example a key that can no longer be
decrypted) raises instead of falling back: users must never silently spend
the platform's quota when they chose their own key.

The returned dict has the same shape as ``settings.ai_provider_config()`` plus
``source`` ("custom"/"default"), so the analyzers and their shared
retry/backoff code work unchanged.
"""

import logging
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import AI_PROVIDER_BASE_URLS, settings
from app.core.encryption import (
    DecryptionError,
    EncryptionUnavailableError,
    decrypt_secret,
    encrypt_secret,
    encryption_available,
)
from app.crud import ai_provider_config as config_crud
from app.models.ai_provider_config import UserAIProviderConfig
from app.schemas.ai_provider import (
    AIProviderConfigResponse,
    AIProviderConfigUpdate,
    AIProviderTestRequest,
    AIProviderTestResult,
)
from app.services.ai.job_analyzer import (
    AIProviderAuthError,
    AIServiceError,
    _build_endpoint_url,
    _build_headers,
    _build_payload,
    _get_client,
    _make_request_with_retry,
)

logger = logging.getLogger(__name__)

#: Shown when a custom key exists but cannot be used.
CUSTOM_KEY_UNREADABLE = (
    "Your saved AI provider key can't be used. Re-enter it in Settings."
)
#: Shown when the user's own provider rejects their key during an analysis.
CUSTOM_KEY_REJECTED = (
    "Your AI provider rejected the API key. Check it in Settings."
)

TEST_OK = "Connection successful."
TEST_REJECTED = "The AI provider rejected the credentials."
TEST_MODEL_UNAVAILABLE = "The model ID was not accepted by the provider."
TEST_UNREACHABLE = "Unable to connect with the provided configuration."


class AIProviderSettingsError(Exception):
    """A Settings request that cannot be fulfilled (safe message)."""

    def __init__(self, message: str, status_code: int = 422) -> None:
        self.message = message
        self.status_code = status_code
        super().__init__(message)


def _custom_config(provider: str, api_key: str, model_id: str) -> dict[str, Any]:
    """Provider config for a user's credentials, on top of platform defaults.

    Only provider, key, model and base URL come from the user; retries,
    timeouts, attribution headers and content limits stay platform-controlled.
    """
    cfg = settings.ai_provider_config()
    cfg.update(
        provider=provider,
        api_key=api_key,
        model=model_id,
        base_url=AI_PROVIDER_BASE_URLS[provider],
    )
    return cfg


def resolve_for_user(db: Session, user_id: int) -> dict[str, Any]:
    """Return the provider config for AI work on ``user_id``'s data.

    Raises:
        AIServiceError: The user's custom key exists but cannot be decrypted.
    """
    config = config_crud.get_config(db, user_id)
    if config is None or not config.is_active:
        cfg = settings.ai_provider_config()
        cfg["source"] = "default"
        return cfg

    try:
        api_key = decrypt_secret(config.api_key_encrypted)
    except (DecryptionError, EncryptionUnavailableError):
        logger.error(
            "Custom AI provider key could not be decrypted: user_id=%s provider=%s",
            user_id,
            config.provider,
        )
        raise AIServiceError(CUSTOM_KEY_UNREADABLE, status_code=502) from None

    cfg = _custom_config(config.provider, api_key, config.model_id)
    cfg["source"] = "custom"
    logger.debug(
        "Using custom AI provider: user_id=%s provider=%s model=%s",
        user_id,
        config.provider,
        config.model_id,
    )
    return cfg


def safe_error_for(cfg: dict[str, Any], exc: AIServiceError) -> AIServiceError:
    """Point a custom-key auth failure at Settings instead of "contact admin"."""
    if cfg.get("source") == "custom" and isinstance(exc, AIProviderAuthError):
        return AIServiceError(CUSTOM_KEY_REJECTED, status_code=502)
    return exc


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------


def _masked(config: UserAIProviderConfig) -> str:
    return f"••••••••{config.api_key_last4}"


def get_status(db: Session, user_id: int) -> AIProviderConfigResponse:
    """Settings view of the user's provider (reads no secrets)."""
    config = config_crud.get_config(db, user_id)
    active = config is not None and config.is_active
    return AIProviderConfigResponse(
        configured=config is not None,
        source="custom" if active else "default",
        provider=config.provider if config else None,
        model_id=config.model_id if config else None,
        masked_api_key=_masked(config) if config else None,
        updated_at=config.updated_at if config else None,
        can_save=encryption_available(),
        supported_providers=list(AI_PROVIDER_BASE_URLS),
    )


def save_config(
    db: Session, user_id: int, payload: AIProviderConfigUpdate
) -> AIProviderConfigResponse:
    """Encrypt and store the user's provider settings.

    Raises:
        AIProviderSettingsError: No key given for a new/changed provider, or
            the server cannot encrypt keys.
    """
    if not encryption_available():
        raise AIProviderSettingsError(
            "Custom AI providers are not enabled on this server.", status_code=503
        )

    existing = config_crud.get_config(db, user_id)
    if payload.api_key is None and (existing is None or existing.provider != payload.provider):
        # A key belongs to one provider: switching provider needs a new key.
        raise AIProviderSettingsError("Enter the API key for this provider.")

    encrypted = last4 = None
    if payload.api_key is not None:
        encrypted = encrypt_secret(payload.api_key)
        last4 = payload.api_key[-4:]

    config_crud.upsert_config(
        db,
        user_id,
        provider=payload.provider,
        model_id=payload.model_id,
        api_key_encrypted=encrypted,
        api_key_last4=last4,
    )
    logger.info(
        "Custom AI provider saved: user_id=%s provider=%s model=%s key_changed=%s",
        user_id,
        payload.provider,
        payload.model_id,
        encrypted is not None,
    )
    return get_status(db, user_id)


def delete_config(db: Session, user_id: int) -> AIProviderConfigResponse:
    """Remove the user's provider; the platform provider is used again."""
    if config_crud.delete_config(db, user_id):
        logger.info("Custom AI provider removed: user_id=%s", user_id)
    return get_status(db, user_id)


async def test_connection(
    db: Session, user_id: int, payload: AIProviderTestRequest
) -> AIProviderTestResult:
    """Send one tiny request with the given credentials; never saves them.

    Without ``api_key`` the saved key is used (same provider only). Provider
    errors are reduced to a safe message; details are logged without secrets.
    """
    api_key = payload.api_key
    if api_key is None:
        existing = config_crud.get_config(db, user_id)
        if existing is None or existing.provider != payload.provider:
            raise AIProviderSettingsError("Enter the API key to test.")
        try:
            api_key = decrypt_secret(existing.api_key_encrypted)
        except (DecryptionError, EncryptionUnavailableError):
            return AIProviderTestResult(ok=False, message=CUSTOM_KEY_UNREADABLE)

    cfg = _custom_config(payload.provider, api_key, payload.model_id)
    cfg["max_retries"] = 0  # a test should answer quickly, not back off
    request_payload = _build_payload(
        cfg,
        'Reply with the JSON object {"ok": true}.',
        system_prompt="You are a connectivity check. Reply with JSON only.",
        max_tokens=20,
    )
    try:
        # Any successful (2xx) reply proves the key and model are usable.
        await _make_request_with_retry(
            _get_client(),
            "POST",
            _build_endpoint_url(cfg),
            json=request_payload,
            headers=_build_headers(cfg),
            cfg=cfg,
        )
    except AIProviderAuthError:
        result = AIProviderTestResult(ok=False, message=TEST_REJECTED)
    except AIServiceError as exc:
        # 400/404 from the provider almost always mean an unknown model.
        message = TEST_MODEL_UNAVAILABLE if exc.status_code in (400, 404) else TEST_UNREACHABLE
        result = AIProviderTestResult(ok=False, message=message)
    else:
        result = AIProviderTestResult(ok=True, message=TEST_OK)

    logger.info(
        "AI provider connection test: user_id=%s provider=%s model=%s ok=%s",
        user_id,
        payload.provider,
        payload.model_id,
        result.ok,
    )
    return result
