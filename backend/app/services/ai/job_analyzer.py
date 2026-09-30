"""AI-powered job vacancy analysis with multi-provider support.

Supports OpenRouter, Groq, and Google Gemini providers.
Handles rate limits (429/503), transient failures, timeout resilience,
and strict JSON parsing.

The module exposes a single public async function ``analyze_vacancy`` and
a small set of domain-specific exceptions that the FastAPI router translates
into controlled HTTP responses (see ``app.routers.jobs``).
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from email.utils import parsedate_to_datetime
from typing import Any, Callable, TypeVar

import httpx
from pydantic import ValidationError

from app.core.config import settings
from app.schemas.application_form import normalise_application_fields
from app.schemas.job import JobAIAnalysisResult

logger = logging.getLogger(__name__)

T = TypeVar("T")

# Transient status codes that warrant a retry.
_RETRYABLE_STATUS_CODES = {429, 502, 503, 504}

# Permanent status codes that should fail immediately.
_PERMANENT_STATUS_CODES = {400, 401, 403, 404}

# Provider-specific base URLs.
_PROVIDER_BASE_URLS = {
    "openrouter": "https://openrouter.ai/api/v1",
    "groq": "https://api.groq.com/openai/v1",
    "gemini": "https://generativelanguage.googleapis.com/v1beta/models",
}

# OpenAI-compatible chat endpoint suffix.
_OPENAI_CHAT_ENDPOINT = "/chat/completions"

# Gemini native API endpoint suffix.
_GEMINI_CHAT_ENDPOINT = ":generateContent"

# Default completion budget for the vacancy-analysis prompt (other AI features
# pass their own, larger budget through ``_build_payload``).
_DEFAULT_MAX_TOKENS = 1000

# A single shared AsyncClient keeps connections alive across calls.
_client: httpx.AsyncClient | None = None


def _get_client() -> httpx.AsyncClient:
    """Return the shared AI HTTP client, creating it once."""
    global _client
    if _client is None:
        cfg = settings.ai_provider_config()
        timeout = cfg["request_timeout"]
        _client = httpx.AsyncClient(timeout=timeout)
    return _client


async def close_ai_client() -> None:
    """Close the shared client and release connections.

    Call during application shutdown (registered in ``app/main.py``).
    Safe to call even when the client was never created.
    """
    global _client
    client = _client
    _client = None
    if client is not None:
        await client.aclose()


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class AIServiceError(Exception):
    """Base exception for AI service errors.

    Carries an HTTP status_code so the FastAPI router can return the right
    response without knowing routing-level details.
    """

    def __init__(self, message: str, status_code: int = 502) -> None:
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class AIProviderUnavailableError(AIServiceError):
    """The AI provider is (temporarily) unavailable."""

    def __init__(self, message: str = "AI service is temporarily unavailable. Please try again.") -> None:
        super().__init__(message, status_code=503)


class AIProviderAuthError(AIServiceError):
    """The AI provider rejected our credentials."""

    def __init__(self, message: str = "AI service authentication failed.") -> None:
        super().__init__(message, status_code=502)


class AIInvalidResponseError(AIServiceError):
    """The AI provider returned a response we could not parse/validate."""

    def __init__(self, message: str = "AI service returned an invalid response.") -> None:
        super().__init__(message, status_code=502)


class AIEmptyResponseError(AIInvalidResponseError):
    """The model answered with nothing usable: empty text or an empty ``{}``.

    Usually a one-off from an overloaded (often free) model, so
    :func:`_request_and_parse` retries it once before giving up.
    """

    def __init__(self, model: str | None = None) -> None:
        self.model = model
        super().__init__(empty_response_message(model))


def empty_response_message(model: str | None) -> str:
    """User-facing explanation of an empty model answer."""
    who = f'The AI model "{model}"' if model else "The AI model"
    return (
        f"{who} returned an empty answer. Try again, or choose another model "
        "in Settings → AI provider."
    )


class AIRateLimitError(AIServiceError):
    """Raised when the provider keeps returning 429.

    ``retry_after`` is how long the provider asked us to wait (seconds), when
    it said so; ``model`` is the model that was rate limited. Both feed the
    user-facing message and the HTTP ``Retry-After`` header.
    """

    def __init__(
        self,
        message: str | None = None,
        *,
        retry_after: float | None = None,
        model: str | None = None,
    ) -> None:
        self.retry_after = retry_after
        self.model = model
        super().__init__(message or rate_limit_message(model, retry_after), status_code=429)


def _describe_wait(seconds: float | None) -> str:
    """Human wording for a wait, rounded up so users do not retry too early."""
    if seconds is None:
        return "about a minute"
    if seconds < 60:
        return f"about {max(5, int(-(-seconds // 5) * 5))} seconds"
    minutes = int(-(-seconds // 60))
    return "about a minute" if minutes == 1 else f"about {minutes} minutes"


def rate_limit_message(model: str | None, retry_after: float | None = None) -> str:
    """User-facing explanation of a provider rate limit.

    Free OpenRouter models (``...:free``) share one rate limit across every
    user of the model, so the useful advice there is to switch models.
    """
    wait = _describe_wait(retry_after)
    if model and model.endswith(":free"):
        return (
            f'The free AI model "{model}" is busy right now: free models share one '
            f"rate limit with everyone using them. Try again in {wait}, or choose a "
            "paid model in Settings → AI provider."
        )
    return f"The AI provider's rate limit was reached. Try again in {wait}."


# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = (
    "You are a job vacancy extraction assistant.\n\n"
    "Analyze the provided vacancy/job requirements.\n"
    "Return ONLY one valid JSON object.\n"
    "Do not use Markdown.\n"
    "Do not use ```json.\n"
    "Do not add explanations before or after the JSON.\n\n"
    "The JSON object MUST contain exactly these fields:\n"
    "{\n"
    '  "company_name": "string",\n'
    '  "position": "string",\n'
    '  "description": "string",\n'
    '  "required_skills": "string",\n'
    '  "required_experience": "string",\n'
    '  "application_fields": [\n'
    '    {"label": "string", "type": "string", "required": boolean,\n'
    '     "description": "string", "options": ["string"]}\n'
    "  ]\n"
    "}\n\n"
    "If information is missing, use an empty string.\n"
    "All fields must be strings.\n"
    "Field types must be one of: text, textarea, email, phone, number, "
    "date, url, select, multi_select, checkbox, file.\n"
    "application_fields is optional: omit it only if you cannot suggest "
    "meaningful questions."
)

_PROMPT_TEMPLATE = """\
Analyze the following job vacancy requirements and extract structured job
information.

Return ONLY a valid JSON object with exactly these fields:
- company_name: string (the hiring company name, or "" if not mentioned)
- position: string (the job title/position, or "" if not mentioned)
- description: string (the job description/responsibilities, or "" if not mentioned)
- required_skills: string (comma-separated list of required skills, or "" if none)
- required_experience: string (experience requirement like "3+ years", or "" if not mentioned)
- application_fields: array of 4-8 questions candidates should answer when
  applying (optional). Each item is an object with:
  - label: string (the question, e.g. "Full name", "Years of experience")
  - type: one of text, textarea, email, phone, number, date, url, select,
    multi_select, checkbox, file
  - required: boolean
  - description: string (short help text, or "")
  - options: array of strings, ONLY for select/multi_select

Rules:
1. Extract ONLY information explicitly present in the vacancy text.
2. Do not invent or hallucinate company names, skills, or experience requirements.
3. If information is not present, use an empty string "".
4. Normalize skills into a comma-separated list with no bullet points.
5. Always include a "Full name" (text), "Email" (email) and "Resume" (file)
   question in application_fields.
6. Return ONLY the JSON object -- no markdown fences, no commentary, no extra text.

Vacancy content:
{vacancy_content}"""


def _build_prompt(vacancy_content: str) -> str:
    """Build the prompt for the AI provider to analyse the vacancy."""
    return _PROMPT_TEMPLATE.format(vacancy_content=vacancy_content)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_MARKDOWN_JSON_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)


def _extract_json_text(content: str) -> str:
    """Try to pull a JSON string out of an LLM response that may be wrapped.

    Handles:
    - Plain JSON:                    {"company_name": "..."}
    - Markdown-wrapped JSON:         ```json {"company_name": "..."} ```
    - Markdown-wrapped JSON (brief): ``` {...} ```
    """
    stripped = content.strip()
    m = _MARKDOWN_JSON_RE.search(stripped)
    if m:
        return m.group(1).strip()
    return stripped


def _strip_json_markdown(text: str) -> str:
    """Return the JSON object text from an LLM reply.

    Handles a Markdown fenced block, and replies where a reasoning model wrote
    its thinking *before* the JSON (some OpenRouter upstreams put it in
    ``content`` instead of a separate field): then the last ``{...}`` object
    that runs to the end of the reply is used. Anything else is returned
    as-is, so the caller's JSON error still reports the real content.
    """
    stripped = text.strip()
    m = _MARKDOWN_JSON_RE.search(stripped)
    if m:
        return m.group(1).strip()
    if stripped.startswith("{"):
        return stripped

    decoder = json.JSONDecoder()
    start = stripped.rfind("{")
    while start != -1:
        try:
            obj, end = decoder.raw_decode(stripped, start)
        except json.JSONDecodeError:
            obj, end = None, -1
        if isinstance(obj, dict) and not stripped[end:].strip():
            return stripped[start:end]
        start = stripped.rfind("{", 0, start)
    return stripped


def _parse_retry_after(response: httpx.Response) -> float | None:
    """Seconds the provider asked us to wait, or None when it did not say.

    Reads, in order:

    * ``Retry-After`` as seconds or as an HTTP date (RFC 9110);
    * ``X-RateLimit-Reset``, which OpenRouter sends for account-level limits,
      as a Unix timestamp in milliseconds or seconds (or a plain delay).
    """
    raw = (response.headers.get("retry-after") or "").strip()
    if raw:
        try:
            return max(0.0, float(raw))
        except ValueError:
            try:
                return max(0.0, parsedate_to_datetime(raw).timestamp() - time.time())
            except (TypeError, ValueError):
                pass

    reset = (response.headers.get("x-ratelimit-reset") or "").strip()
    if reset:
        try:
            value = float(reset)
        except ValueError:
            return None
        if value > 1e11:  # Unix time in milliseconds (as seconds this is year 5138)
            return max(0.0, value / 1000 - time.time())
        if value > 1e9:  # Unix time in seconds
            return max(0.0, value - time.time())
        return max(0.0, value)
    return None


def _error_reason(response: httpx.Response, limit: int = 300) -> str:
    """Extract a short, sanitized provider error message from the response body.

    Used for server-side logging only, so operators can tell an upstream
    rate limit apart from a bad request, auth failure, or model problem.
    Reads the response body only -- never headers or credentials -- and is
    collapsed to one line and truncated to ``limit`` characters.
    """
    try:
        data = response.json()
    except (json.JSONDecodeError, ValueError):
        data = None

    reason = ""
    if isinstance(data, dict):
        error = data.get("error")
        if isinstance(error, dict):
            # OpenAI-compatible shape, plus OpenRouter's metadata.raw which
            # carries the upstream provider's own message.
            parts = [error.get("message")]
            metadata = error.get("metadata")
            if isinstance(metadata, dict):
                parts.append(metadata.get("raw"))
            parts = [p for p in parts if isinstance(p, str) and p.strip()]
            if parts:
                reason = " | ".join(parts)
        elif isinstance(error, str):
            reason = error
    if not reason:
        reason = (response.text or "").strip()

    reason = " ".join(reason.split())
    if len(reason) > limit:
        reason = reason[:limit] + "..."
    return reason


def _get_retry_delay(attempt: int, retry_base_delay: float, retry_after: float | None) -> float:
    """Delay before the next attempt.

    The provider's own instruction (``retry_after``) wins: retrying sooner is
    guaranteed to be rejected again. Without one, exponential backoff:
    ``retry_base_delay * 2 ** attempt``. Whether the wait is acceptable at all
    (per-wait cap, total budget) is decided by the caller.
    """
    if retry_after is not None:
        return retry_after
    return retry_base_delay * (2 ** attempt)


def _is_retryable_status(status_code: int) -> bool:
    """Return True if the HTTP status code warrants a retry."""
    return status_code in _RETRYABLE_STATUS_CODES


def _is_permanent_status(status_code: int) -> bool:
    """Return True if the HTTP status code should fail immediately."""
    return status_code in _PERMANENT_STATUS_CODES


def _build_headers(cfg: dict[str, Any]) -> dict[str, str]:
    """Build HTTP headers for the AI provider request."""
    provider = cfg["provider"]
    headers: dict[str, str] = {
        "Authorization": f"Bearer {cfg['api_key']}",
        "Content-Type": "application/json",
    }
    if provider in ("openrouter", "groq"):
        headers["HTTP-Referer"] = cfg["http_referer"]
        headers["X-Title"] = cfg["app_title"]
    return headers


def _build_payload(
    cfg: dict[str, Any],
    prompt: str,
    *,
    system_prompt: str = _SYSTEM_PROMPT,
    max_tokens: int = _DEFAULT_MAX_TOKENS,
) -> dict[str, Any]:
    """Build the request payload for the AI provider.

    ``system_prompt``/``max_tokens`` default to the vacancy-analysis values so
    every other AI feature (e.g. application analysis) reuses this single
    provider payload builder instead of duplicating provider knowledge.
    """
    provider = cfg["provider"]
    model = cfg["model"]

    if provider == "gemini":
        return {
            "contents": [
                {
                    "parts": [
                        {"text": f"{system_prompt}\n\n{prompt}"}
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.1,
                "maxOutputTokens": max_tokens,
            },
        }

    # OpenAI-compatible providers (OpenRouter, Groq)
    payload: dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.1,
        "max_tokens": max_tokens,
        "response_format": {"type": "json_object"},
    }
    if provider == "openrouter":
        # Hybrid reasoning models (e.g. deepseek/deepseek-v4.1-flash) think by
        # default, and some upstreams (Together) stream that thinking into
        # ``content``: it eats the whole ``max_tokens`` budget and no JSON is
        # ever produced. These are extraction tasks, so turn thinking off.
        # OpenRouter ignores the flag for models that cannot disable it.
        payload["reasoning"] = {"enabled": False}
    return payload


def _build_endpoint_url(cfg: dict[str, Any]) -> str:
    """Return the chat-completions URL for the configured provider."""
    base_url = cfg["base_url"].rstrip("/")
    if cfg["provider"] == "gemini":
        # Gemini native API: base_url/model:generateContent
        return f"{base_url}/{cfg['model']}{_GEMINI_CHAT_ENDPOINT}"
    # OpenAI-compatible providers.
    return f"{base_url}{_OPENAI_CHAT_ENDPOINT}"


def _parse_response(response: httpx.Response, cfg: dict[str, Any]) -> str:
    """Extract the AI response text from the provider response.

    Returns the raw text content for JSON parsing.
    Raises AIInvalidResponseError if the response shape is unexpected.
    """
    provider = cfg["provider"]

    try:
        response_data = response.json()
    except (json.JSONDecodeError, ValueError):
        snippet = (response.text or "")[:200]
        logger.exception(
            "AI provider returned non-JSON body (first 200 chars): %r", snippet
        )
        raise AIInvalidResponseError()

    if provider == "gemini":
        try:
            candidates = response_data.get("candidates")
            if not candidates or not isinstance(candidates, list):
                logger.error("Gemini response missing candidates: %s", json.dumps(response_data, ensure_ascii=False)[:300])
                raise AIInvalidResponseError()
            content = candidates[0].get("content", {})
            parts = content.get("parts", [])
            if not parts:
                logger.error("Gemini response has no text parts")
                raise AIInvalidResponseError()
            text = parts[0].get("text", "")
        except (KeyError, IndexError, TypeError) as exc:
            logger.error("Gemini response missing expected shape: %s", json.dumps(response_data, ensure_ascii=False)[:300])
            raise AIInvalidResponseError() from exc
        if not isinstance(text, str) or not text.strip():
            logger.warning("Gemini returned empty message content: model=%s", cfg.get("model"))
            raise AIEmptyResponseError(cfg.get("model"))
        return text

    # OpenAI-compatible providers (OpenRouter, Groq)
    try:
        content = response_data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        logger.error(
            "AI provider response missing expected shape: %s",
            json.dumps(response_data, ensure_ascii=False)[:300],
        )
        raise AIInvalidResponseError()

    if not isinstance(content, str) or not content.strip():
        logger.warning(
            "AI provider returned empty message content: provider=%s model=%s",
            provider,
            cfg.get("model"),
        )
        raise AIEmptyResponseError(cfg.get("model"))
    if response_data["choices"][0].get("finish_reason") == "length":
        # Not fatal by itself (the JSON may still be complete), but it is the
        # usual reason for a "not valid JSON" error that follows.
        logger.warning(
            "AI provider stopped at max_tokens (model=%s); the reply may be truncated",
            cfg.get("model"),
        )
    return content


def _parse_job_response(text: str, model: str | None = None) -> JobAIAnalysisResult:
    """Parse and validate the AI response text into a JobAIAnalysisResult.

    Strips Markdown fences, parses JSON, and validates through Pydantic.
    Suggested ``application_fields`` are normalised against the fixed
    field-type registry: unknown types/malformed entries are dropped here so
    AI output can never inject anything unexpected into the public form.
    Raises AIInvalidResponseError on any failure.
    """
    raw_json = _strip_json_markdown(text)

    try:
        parsed = json.loads(raw_json)
    except json.JSONDecodeError:
        snippet = raw_json[:200]
        logger.exception(
            "AI provider response content is not valid JSON (first 200 chars): %r",
            snippet,
        )
        raise AIInvalidResponseError(
            "AI service returned a response that is not valid JSON."
        )

    if parsed == {}:
        raise AIEmptyResponseError(model)

    try:
        result = JobAIAnalysisResult.model_validate(parsed)
    except ValidationError as exc:
        logger.exception("AI response failed Pydantic validation: model=%s %s", model, exc)
        raise AIInvalidResponseError(
            "AI service returned data that does not match the expected format."
        )

    # Normalise the AI's application-field suggestions against the fixed
    # registry (lenient: invalid entries are dropped, never raise). The
    # public form's UI is unaffected by whatever a model returns here.
    if parsed and isinstance(parsed.get("application_fields"), list):
        normalised = normalise_application_fields(parsed["application_fields"])
        # Only expose suggestions when at least one usable field survived.
        result.application_fields = normalised or None

    return result


# ---------------------------------------------------------------------------
# Retry wrapper
# ---------------------------------------------------------------------------

async def _make_request_with_retry(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    *,
    json: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    cfg: dict[str, Any],
) -> httpx.Response:
    """Make an HTTP request with retry logic for transient failures.

    Retries on 429, 502, 503, 504 and network errors.
    Honors Retry-After headers when present.
    Does NOT retry on 400, 401, 403, 404.
    """
    max_retries = cfg["max_retries"]
    retry_base_delay = cfg["retry_base_delay"]
    # Always present in configs built by Settings.ai_provider_config().
    max_retry_wait = cfg.get("max_retry_wait", 30)
    retry_budget = cfg.get("retry_budget", 45)
    provider = cfg["provider"]
    model = cfg.get("model")
    waited = 0.0

    for attempt in range(max_retries + 1):
        try:
            response = await client.post(
                url,
                json=json,
                headers=headers,
            )
        except httpx.TimeoutException:
            logger.warning("AI provider request timed out (provider=%s)", provider)
            if attempt >= max_retries:
                raise AIProviderUnavailableError(
                    "AI service did not respond in time. Please try again later."
                ) from None
            continue
        except httpx.NetworkError:
            logger.warning("AI provider network error (provider=%s)", provider)
            if attempt >= max_retries:
                raise AIProviderUnavailableError() from None
            continue
        except httpx.RequestError:
            logger.exception("Unexpected HTTP client error calling AI provider (provider=%s)", provider)
            if attempt >= max_retries:
                raise AIProviderUnavailableError() from None
            continue
        except Exception:
            logger.exception("Unexpected error calling AI provider (provider=%s)", provider)
            if attempt >= max_retries:
                raise AIProviderUnavailableError() from None
            continue

        status_code = response.status_code

        # Permanent errors: fail immediately, no retry.
        if _is_permanent_status(status_code):
            reason = _error_reason(response)
            if status_code == 401:
                logger.error(
                    "AI provider authentication failed (provider=%s, status=%s, reason=%s)",
                    provider,
                    status_code,
                    reason,
                )
                raise AIProviderAuthError()
            elif status_code == 403:
                logger.error(
                    "AI provider forbidden (provider=%s, status=%s, reason=%s)",
                    provider,
                    status_code,
                    reason,
                )
                raise AIProviderAuthError("AI provider access forbidden.")
            elif status_code == 400:
                logger.error(
                    "AI provider returned bad request (provider=%s, status=%s, reason=%s)",
                    provider,
                    status_code,
                    reason,
                )
                raise AIServiceError(
                    "AI provider rejected the request. Please check your configuration.",
                    status_code=400,
                )
            elif status_code == 404:
                logger.error(
                    "AI provider endpoint not found (provider=%s, status=%s, reason=%s)",
                    provider,
                    status_code,
                    reason,
                )
                raise AIServiceError(
                    "AI provider endpoint not found.",
                    status_code=404,
                )

        # Retryable errors.
        if _is_retryable_status(status_code):
            retry_after = _parse_retry_after(response)
            delay = _get_retry_delay(attempt, retry_base_delay, retry_after)

            log_parts = [
                f"provider={provider}",
                f"status={status_code}",
                f"attempt={attempt}/{max_retries}",
            ]
            if retry_after is not None:
                log_parts.append(f"retry_after={retry_after}")
            log_parts.append(f"reason={_error_reason(response)}")
            logger.warning("AI provider request failed; %s", " ".join(log_parts))

            # Retry only while the wait is one we are willing to make: not
            # longer than the per-wait cap when the provider set it, and
            # within the call's total waiting budget.
            too_long = retry_after is not None and retry_after > max_retry_wait
            over_budget = waited + delay > retry_budget
            if attempt < max_retries and not too_long and not over_budget:
                await asyncio.sleep(delay)
                waited += delay
                continue

            # Giving up.
            if status_code == 429:
                logger.warning(
                    "AI provider rate limit, giving up: provider=%s model=%s status=%s "
                    "attempts=%d waited=%.0fs retry_after=%s reason=%s",
                    provider,
                    model,
                    status_code,
                    attempt + 1,
                    waited,
                    retry_after,
                    _error_reason(response),
                )
                raise AIRateLimitError(retry_after=retry_after, model=model)
            else:
                logger.warning(
                    "AI provider unavailable: provider=%s status=%s attempts=%d",
                    provider,
                    status_code,
                    max_retries + 1,
                )
                raise AIProviderUnavailableError()

        # Successful response.
        if 200 <= status_code < 300:
            return response

        # Unexpected status code.
        logger.error(
            "AI provider returned unexpected status %s (provider=%s, reason=%s)",
            status_code,
            provider,
            _error_reason(response),
        )
        raise AIProviderUnavailableError(
            f"AI service returned an unexpected error (status {status_code})."
        )

    # Should not reach here, but satisfy type checker.
    raise AIProviderUnavailableError()


#: Extra attempts after an empty answer (see :class:`AIEmptyResponseError`).
_EMPTY_ANSWER_RETRIES = 1


async def _request_and_parse(
    client: httpx.AsyncClient,
    url: str,
    *,
    payload: dict[str, Any],
    headers: dict[str, str],
    cfg: dict[str, Any],
    parse: Callable[[str, str | None], T],
) -> T:
    """Send one AI request and parse its reply with ``parse(text, model)``.

    Shared by every AI feature. An empty answer (no text, or ``{}``) is
    retried once, since overloaded models return one now and then; every other
    failure is raised at once. Transport retries (429/503/network) happen
    inside :func:`_make_request_with_retry` as before.
    """
    model = cfg.get("model")
    for attempt in range(_EMPTY_ANSWER_RETRIES + 1):
        response = await _make_request_with_retry(
            client, "POST", url, json=payload, headers=headers, cfg=cfg
        )
        try:
            return parse(_parse_response(response, cfg), model)
        except AIEmptyResponseError:
            logger.warning(
                "AI model returned an empty answer: provider=%s model=%s attempt=%d/%d",
                cfg["provider"],
                model,
                attempt + 1,
                _EMPTY_ANSWER_RETRIES + 1,
            )
            if attempt == _EMPTY_ANSWER_RETRIES:
                raise AIEmptyResponseError(model) from None
    raise AssertionError("unreachable")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def analyze_vacancy(vacancy_content: str, *, cfg: dict[str, Any]) -> JobAIAnalysisResult:
    """Analyse a vacancy using the configured AI provider and return structured job information.

    Args:
        vacancy_content: The full vacancy / job-requirement text to analyse.
        cfg: The requesting user's provider config from
            ``app.services.ai.provider.resolve_for_user``. Required, so no AI
            call can bypass the per-user credential resolution.

    Returns:
        JobAIAnalysisResult with the extracted company_name, position,
        description, required_skills and required_experience.

    Raises:
        AIServiceError: On failure modes (timeout, auth, rate limit, invalid
            response, etc.)  The FastAPI router catches this and renders an
            ``HTTPException`` with the matching status code and detail.
    """
    if not vacancy_content or not vacancy_content.strip():
        raise AIServiceError("Vacancy content cannot be empty.", status_code=422)

    max_content_length = cfg["max_content_length"]
    if len(vacancy_content) > max_content_length:
        raise AIServiceError(
            "Vacancy content exceeds the maximum length of "
            f"{max_content_length} characters.",
            status_code=422,
        )

    api_key = cfg["api_key"]
    if not api_key:
        logger.error(
            "AI API key not configured -- refusing to call the AI provider"
        )
        raise AIProviderAuthError(
            "AI service is not configured. Please contact the administrator."
        )

    prompt = _build_prompt(vacancy_content)
    headers = _build_headers(cfg)
    payload = _build_payload(cfg, prompt)
    provider = cfg["provider"]

    # Provider-specific chat endpoint.
    url = _build_endpoint_url(cfg)

    client = _get_client()

    result = await _request_and_parse(
        client, url, payload=payload, headers=headers, cfg=cfg, parse=_parse_job_response
    )

    logger.info(
        "AI request succeeded: provider=%s model=%s",
        provider,
        cfg["model"],
    )

    return result
