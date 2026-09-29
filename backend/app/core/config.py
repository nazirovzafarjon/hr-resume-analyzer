"""Application configuration loaded from environment variables.

Uses Pydantic Settings. Values can be provided through the `.env` file
or real environment variables.
"""

from typing import Any

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings."""

    # General
    APP_NAME: str = "Resume Analyzer API"
    DEBUG: bool = False
    API_PREFIX: str = "/api"

    # Security
    SECRET_KEY: str = "change-me-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    # Refresh tokens live longer than access tokens and are only ever exchanged
    # at POST /api/auth/refresh (never accepted as an Authorization bearer).
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    # Short-lived, single-purpose token embedded in the password-reset link.
    PASSWORD_RESET_TOKEN_EXPIRE_MINUTES: int = 30
    # Base URL of the frontend, used to build the absolute reset link that is
    # emailed to the user (e.g. http://localhost:5173/reset-password?token=...).
    FRONTEND_BASE_URL: str = "http://localhost:5173"

    # Resend (transactional email — password reset delivery)
    # Secret API key from https://resend.com/api-keys. When it is empty the app
    # stays fully usable in development: reset links are written to the server
    # log instead of being emailed.
    RESEND_API_KEY: str = ""
    # Verified from-address. The `onboarding@resend.dev` sandbox sender ships
    # with every Resend account but may only deliver to the address the account
    # was registered with; use a verified custom domain for real users.
    EMAIL_FROM: str = "onboarding@resend.dev"

    # Google OAuth 2.0 (Sign in with Google)
    # Client ID/secret from the Google Cloud Console. The redirect URI is the
    # frontend callback route the user lands back on after the consent screen
    # and must also be registered as an authorized redirect URI in the console.
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_REDIRECT_URI: str = "http://localhost:5173/oauth/callback"

    # Superuser seed (created on startup when set and no superuser exists yet)
    SUPERUSER_EMAIL: str = ""
    SUPERUSER_PASSWORD: str = ""
    SUPERUSER_FULL_NAME: str = "Administrator"

    # Database
    DATABASE_URL: str = (
        "postgresql://postgres:postgres@localhost:5432/resume_analyzer"
    )

    # CORS - comma-separated list of browser origins allowed to call this API.
    # Both Vite dev servers must be listed: the CRM (http://localhost:5173) and
    # the landing site (http://localhost:5174, for its public Contact form).
    BACKEND_CORS_ORIGINS: str = "http://localhost:5173,http://localhost:5174"

    # OpenRouter (AI provider for job vacancy analysis)
    # Get an API key at https://openrouter.ai/keys
    OPENROUTER_API_KEY: str = ""
    OPENROUTER_MODEL: str = "google/gemma-4-26b-a4b-it:free"
    # Site URL reported to OpenRouter for attribute tracking. Used as the
    # HTTP-Referer header value. Must be an absolute URL.
    OPENROUTER_REFERER: str = "http://localhost:8000"
    # Application title reported to OpenRouter in the X-Title header.
    OPENROUTER_APP_TITLE: str = "Resume Analyzer"
    # Maximum accepted length of vacancy_content passed to the AI provider.
    OPENROUTER_MAX_CONTENT_LENGTH: int = 50000
    # Maximum number of resume characters sent to the AI provider when an
    # application is analysed (job requirements + form answers + resume).
    # Longer resumes are truncated so the prompt stays inside the provider's
    # context window instead of failing the whole analysis.
    APPLICATION_RESUME_MAX_CHARS: int = 20000

    # AI provider configuration (general, provider-agnostic).
    # These take precedence over provider-specific legacy variables.
    # Supported providers: openrouter, groq, gemini
    AI_PROVIDER: str = "openrouter"
    # Model identifier. For OpenRouter use "provider/model:free" format.
    # For Groq use "llama-3.3-70b-versatile" etc. For Gemini use "gemini-2.0-flash".
    AI_MODEL: str = ""
    # API key for the configured AI provider.
    AI_API_KEY: str = ""
    # Base URL for the AI provider's OpenAI-compatible API.
    # Leave empty to use the provider's default.
    AI_BASE_URL: str = ""
    # Maximum number of retry attempts for transient failures (429, 503, network).
    AI_MAX_RETRIES: int = 3
    # Base delay in seconds for exponential backoff between retries.
    AI_RETRY_BASE_DELAY: int = 2
    # Request timeout in seconds.
    AI_REQUEST_TIMEOUT: int = 60
    # HTTP-Referer header value for AI provider attribution.
    AI_HTTP_REFERER: str = ""
    # X-Title header value for AI provider attribution.
    AI_APP_TITLE: str = "Resume Analyzer"

    # Profile images (local storage, served from the /uploads static mount)
    # Directory that stores uploaded files (profile images), relative to the
    # directory the backend is started from.
    UPLOAD_DIR: str = "uploads"
    # Maximum accepted size for a profile image upload, in megabytes.
    PROFILE_IMAGE_MAX_SIZE_MB: int = 5

    @field_validator("DEBUG", mode="before")
    @classmethod
    def parse_debug(cls, value: Any) -> Any:
        """Accept common environment names in addition to booleans."""
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"debug", "development", "dev"}:
                return True
            if normalized in {"release", "production", "prod"}:
                return False
        return value

    def ai_provider_config(self) -> dict[str, Any]:
        """Return resolved AI provider configuration with backward compatibility.

        Precedence:
            1. AI_* explicit configuration (AI_PROVIDER, AI_MODEL, etc.)
            2. Provider-specific legacy configuration (OPENROUTER_API_KEY, etc.)
            3. Safe defaults

        Supported providers: openrouter, groq, gemini
        """
        provider = self.AI_PROVIDER

        # Resolve API key: AI_API_KEY takes precedence, then provider-specific
        api_key = self.AI_API_KEY or ""
        if not api_key and provider == "openrouter":
            api_key = self.OPENROUTER_API_KEY

        # Resolve model: AI_MODEL takes precedence, then provider-specific
        model = self.AI_MODEL or ""
        if not model and provider == "openrouter":
            model = self.OPENROUTER_MODEL

        # Resolve base URL: AI_BASE_URL takes precedence, then provider default
        base_url = self.AI_BASE_URL or ""
        if not base_url:
            if provider == "openrouter":
                base_url = "https://openrouter.ai/api/v1"
            elif provider == "groq":
                base_url = "https://api.groq.com/openai/v1"
            elif provider == "gemini":
                base_url = "https://generativelanguage.googleapis.com/v1beta/models"

        # Resolve referer and title
        http_referer = self.AI_HTTP_REFERER or self.OPENROUTER_REFERER
        app_title = self.AI_APP_TITLE or self.OPENROUTER_APP_TITLE

        # Resolve max content length
        max_content_length = self.OPENROUTER_MAX_CONTENT_LENGTH

        return {
            "provider": provider,
            "model": model,
            "api_key": api_key,
            "base_url": base_url,
            "max_retries": self.AI_MAX_RETRIES,
            "retry_base_delay": self.AI_RETRY_BASE_DELAY,
            "request_timeout": self.AI_REQUEST_TIMEOUT,
            "http_referer": http_referer,
            "app_title": app_title,
            "max_content_length": max_content_length,
        }

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
