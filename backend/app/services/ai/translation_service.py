"""AI-powered translation service for HR candidate analysis details.

Translates structured evaluation data (summaries, strengths, weaknesses, risks,
requirements, skills) into the target language requested by the UI.

CRITICAL:
- This is a presentation-layer service only.
- It NEVER mutates or writes to PostgreSQL (applications.ai_analysis_details
  and jobs remain unaltered in their canonical language).
- Utilizes in-memory caching to prevent repetitive LLM calls and avoid rate limits.
"""

from __future__ import annotations

import hashlib
import json
import logging
from collections import OrderedDict
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import settings
from app.services.ai import provider as provider_service
from app.services.ai.job_analyzer import (
    AIEmptyResponseError,
    AIInvalidResponseError,
    AIServiceError,
    _build_endpoint_url,
    _build_headers,
    _build_payload,
    _get_client,
    _request_and_parse,
    _strip_json_markdown,
)

logger = logging.getLogger(__name__)

#: Completion budget for translating analysis payloads.
_TRANSLATION_MAX_TOKENS = 3000

#: Language code to descriptive name mapping.
LANGUAGE_NAMES: dict[str, str] = {
    "uz": "Uzbek (Latin script / O'zbek tili)",
    "kiril": "Uzbek (Cyrillic script / Ўзбек тили)",
    "ru": "Russian (Русский язык)",
    "en": "English",
}

#: Maximum items in server-side translation cache.
_CACHE_MAX_ITEMS = 1000

# Thread-safe in-memory LRU-like cache (OrderedDict)
_translation_cache: OrderedDict[str, dict[str, Any]] = OrderedDict()


def _get_cache_key(target_language: str, payload: dict[str, Any]) -> str:
    """Generate a deterministic cache key based on language and payload."""
    serialized = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    hasher = hashlib.sha256()
    hasher.update(target_language.strip().lower().encode("utf-8"))
    hasher.update(b":")
    hasher.update(serialized.encode("utf-8"))
    return hasher.hexdigest()


def _get_cached_translation(key: str) -> dict[str, Any] | None:
    """Retrieve a cached translation result if present."""
    if key in _translation_cache:
        # Move to end (most recently used)
        _translation_cache.move_to_end(key)
        return _translation_cache[key]
    return None


def _set_cached_translation(key: str, value: dict[str, Any]) -> None:
    """Store a translation result in cache, maintaining max capacity."""
    if key in _translation_cache:
        _translation_cache.move_to_end(key)
    _translation_cache[key] = value
    if len(_translation_cache) > _CACHE_MAX_ITEMS:
        _translation_cache.popitem(last=False)


def clear_translation_cache() -> None:
    """Clear all cached translations (used in testing)."""
    _translation_cache.clear()


def _has_translatable_content(payload: dict[str, Any]) -> bool:
    """Return True if any field in the payload contains non-empty text."""
    for value in payload.values():
        if isinstance(value, str) and value.strip():
            return True
        if isinstance(value, list) and any(
            isinstance(item, str) and item.strip() for item in value
        ):
            return True
    return False


def _parse_translation_response(text: str, model: str | None = None) -> dict[str, Any]:
    """Parse and validate the translation JSON returned by the LLM."""
    raw_json = _strip_json_markdown(text)
    try:
        parsed = json.loads(raw_json)
    except json.JSONDecodeError:
        logger.error(
            "AI translation output is not valid JSON (first 200 chars): %r",
            raw_json[:200],
        )
        raise AIInvalidResponseError(
            "AI translation service returned a response that is not valid JSON."
        )

    if not isinstance(parsed, dict):
        logger.error("AI translation output is not a JSON object")
        raise AIInvalidResponseError(
            "AI translation service returned data that is not a JSON object."
        )

    return parsed


async def translate_analysis_payload(
    payload: dict[str, Any],
    target_language: str,
    current_user_id: int,
    db: Session,
) -> tuple[dict[str, Any], bool]:
    """Translate an application analysis payload into target_language on-the-fly.

    Returns:
        tuple of (translated_payload_dict, is_cached_bool).

    Guarantees:
        - NEVER writes or mutates the database.
        - Preserves all input keys.
        - Falls back to original text for individual fields if not present in LLM response.
    """
    clean_target = target_language.strip().lower()
    target_desc = LANGUAGE_NAMES.get(clean_target, clean_target)

    # 1. Fast path: Empty or non-translatable payload
    if not payload or not _has_translatable_content(payload):
        return payload, False

    # 2. Check server-side memory cache
    cache_key = _get_cache_key(clean_target, payload)
    cached = _get_cached_translation(cache_key)
    if cached is not None:
        logger.debug("Translation cache HIT for language=%s", clean_target)
        return cached, True

    # 3. Resolve AI provider configuration for the requesting user
    try:
        cfg = provider_service.resolve_for_user(db, current_user_id)
    except provider_service.AIConfigurationRequiredError:
        # Check platform default fallback
        cfg = settings.ai_provider_config()
        if not cfg.get("api_key"):
            raise provider_service.AIConfigurationRequiredError()
        cfg["source"] = "default"

    if not cfg.get("api_key"):
        raise AIServiceError(
            "AI translation is not configured. Please add an API key in Settings → AI provider.",
            status_code=400,
        )

    # 4. Construct prompts adhering to prompt instructions
    system_prompt = (
        f"You are a translation engine for HR evaluation data. "
        f"Translate all text values into {target_desc}. "
        f"Maintain the exact JSON schema and keys. Do NOT evaluate or alter facts. "
        f"Return ONLY valid JSON matching the exact schema."
    )

    user_prompt = (
        f"Translate the following JSON object into {target_desc}. "
        f"Keep all keys identical. Translate all strings and string lists:\n\n"
        f"{json.dumps(payload, ensure_ascii=False, indent=2)}"
    )

    request_payload = _build_payload(
        cfg,
        user_prompt,
        system_prompt=system_prompt,
        max_tokens=_TRANSLATION_MAX_TOKENS,
    )
    headers = _build_headers(cfg)
    url = _build_endpoint_url(cfg)
    client = _get_client()

    try:
        translated = await _request_and_parse(
            client,
            url,
            payload=request_payload,
            headers=headers,
            cfg=cfg,
            parse=_parse_translation_response,
        )
    except Exception as exc:
        if isinstance(exc, AIServiceError):
            raise provider_service.safe_error_for(cfg, exc) from exc
        raise

    # 5. Ensure all keys from input payload are preserved
    merged_result: dict[str, Any] = {}
    for key, original_val in payload.items():
        if key in translated and translated[key] is not None:
            merged_result[key] = translated[key]
        else:
            merged_result[key] = original_val

    # 6. Save in cache
    _set_cached_translation(cache_key, merged_result)

    logger.info(
        "AI analysis translated successfully: target=%s keys=%d provider=%s",
        clean_target,
        len(merged_result),
        cfg.get("provider"),
    )

    return merged_result, False
