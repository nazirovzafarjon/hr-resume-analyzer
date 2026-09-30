"""Runtime platform settings and the read-only configuration overview.

Two kinds of settings are shown on the admin Settings page:

* **Runtime switches** (``platform_settings`` table) that an admin may change,
  e.g. whether new accounts can register. Every change is audited.
* **Environment configuration** (``app.core.config``) shown read-only as
  *status*: which provider/model is configured, whether email delivery or
  Google sign-in is set up. Secrets are never returned, not even masked;
  the API only says whether a value is present.
"""

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import AI_PROVIDER_BASE_URLS, settings
from app.core.encryption import encryption_available
from app.crud import platform_settings as settings_crud
from app.models.ai_provider_config import UserAIProviderConfig
from app.models.platform_settings import PlatformSettings
from app.models.user import User
from app.services import audit
from app.services.audit import AuditAction, AuditContext, AuditResource

#: Fields an admin may change at runtime (anything else is rejected by schema).
EDITABLE_FIELDS = ("registration_enabled",)


def get_settings(db: Session) -> PlatformSettings:
    return settings_crud.get_or_create(db)


def registration_enabled(db: Session) -> bool:
    """Whether new accounts may be created right now."""
    return get_settings(db).registration_enabled


def update_settings(
    db: Session,
    admin: User,
    changes: dict[str, Any],
    context: AuditContext | None = None,
) -> PlatformSettings:
    """Apply admin changes and audit exactly what changed (old -> new)."""
    row = get_settings(db)
    diff = {
        key: value
        for key, value in changes.items()
        if key in EDITABLE_FIELDS and getattr(row, key) != value
    }
    if not diff:
        return row
    previous = {key: getattr(row, key) for key in diff}
    row = settings_crud.update(db, row, {**diff, "updated_by_id": admin.id})
    audit.record(
        db,
        AuditAction.UPDATE_SETTINGS,
        resource_type=AuditResource.SETTINGS,
        actor=admin,
        details={
            **{f"{key}_from": previous[key] for key in diff},
            **{f"{key}_to": value for key, value in diff.items()},
        },
        context=context,
    )
    return row


def configuration_overview(db: Session) -> dict[str, Any]:
    """Environment configuration as safe status flags (no secret values)."""
    ai = settings.ai_provider_config()
    custom_provider_users = db.execute(
        select(func.count(UserAIProviderConfig.id)).where(UserAIProviderConfig.is_active.is_(True))
    ).scalar_one()
    return {
        "platform": {
            "app_name": settings.APP_NAME,
            "debug": settings.DEBUG,
            "frontend_url": settings.FRONTEND_BASE_URL,
        },
        "ai": {
            "provider": ai["provider"],
            "model": ai["model"] or None,
            "api_key_configured": bool(ai["api_key"]),
            # A flag, not the URL itself: a custom base URL could embed credentials.
            "uses_default_base_url": not settings.AI_BASE_URL
            or settings.AI_BASE_URL == AI_PROVIDER_BASE_URLS.get(ai["provider"]),
            "max_retries": ai["max_retries"],
            "retry_base_delay_seconds": ai["retry_base_delay"],
            "request_timeout_seconds": ai["request_timeout"],
            "custom_keys_enabled": encryption_available(),
            "custom_provider_users": int(custom_provider_users),
            "supported_providers": list(AI_PROVIDER_BASE_URLS),
        },
        "email": {
            "provider": "resend",
            "configured": bool(settings.RESEND_API_KEY),
            "sender_configured": bool(settings.EMAIL_FROM),
            # The shared sandbox sender can only deliver to the account owner.
            "sandbox_sender": settings.EMAIL_FROM == "onboarding@resend.dev",
        },
        "auth": {
            "google_sign_in_configured": bool(
                settings.GOOGLE_CLIENT_ID and settings.GOOGLE_CLIENT_SECRET
            ),
            "access_token_minutes": settings.ACCESS_TOKEN_EXPIRE_MINUTES,
            "refresh_token_days": settings.REFRESH_TOKEN_EXPIRE_DAYS,
            # A deployment still on the placeholder key can have its tokens forged.
            "secret_key_is_default": settings.SECRET_KEY == "change-me-in-production",
        },
    }
