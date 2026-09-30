"""Pydantic schemas for Settings -> "Connect your provider and API key".

Responses never contain the API key: only whether one is saved and a masked
hint built from its last four characters.
"""

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, StringConstraints

from app.core.config import AI_PROVIDER_BASE_URLS

#: Providers a user may configure (same set the platform supports).
AIProviderName = Literal["openrouter", "groq", "gemini"]
assert set(AIProviderName.__args__) == set(AI_PROVIDER_BASE_URLS)  # keep in sync

ApiKeyStr = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=8, max_length=500, pattern=r"^\S+$")
]
ModelIdStr = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200, pattern=r"^\S+$")
]


class AIProviderConfigUpdate(BaseModel):
    """Save or update the user's provider.

    ``api_key`` may be omitted when a key is already saved (e.g. to change only
    the model); it is required the first time.
    """

    provider: AIProviderName
    model_id: ModelIdStr
    api_key: ApiKeyStr | None = None


class AIProviderTestRequest(BaseModel):
    """Try a configuration without saving it.

    Without ``api_key`` the saved key is used, provided the provider matches.
    """

    provider: AIProviderName
    model_id: ModelIdStr
    api_key: ApiKeyStr | None = None


class AIProviderTestResult(BaseModel):
    """Outcome of a connection test (message is always safe to show)."""

    ok: bool
    message: str


class AIProviderConfigResponse(BaseModel):
    """The user's provider settings as shown in Settings (no secrets)."""

    configured: bool
    #: "custom" when the user's own provider is used, "default" otherwise.
    source: Literal["custom", "default"]
    provider: str | None = None
    model_id: str | None = None
    masked_api_key: str | None = None
    updated_at: datetime | None = None
    #: False when the server has no encryption key, so keys cannot be saved.
    can_save: bool
    #: True when AI features need the user's own configuration (no platform
    #: fallback; ``REQUIRE_USER_AI_CONFIG``).
    required: bool = False
    supported_providers: list[str]
