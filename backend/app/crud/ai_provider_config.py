"""CRUD operations for users' AI provider configurations.

Contains only database access, always scoped to one ``user_id``.
Encryption and provider logic live in ``app.services.ai.provider``.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.ai_provider_config import UserAIProviderConfig


def get_config(db: Session, user_id: int) -> UserAIProviderConfig | None:
    """Return the user's configuration, or ``None``."""
    return db.execute(
        select(UserAIProviderConfig).where(UserAIProviderConfig.user_id == user_id)
    ).scalar_one_or_none()


def upsert_config(
    db: Session,
    user_id: int,
    *,
    provider: str,
    model_id: str,
    api_key_encrypted: str | None,
    api_key_last4: str | None,
) -> UserAIProviderConfig:
    """Create or update the user's configuration.

    ``api_key_encrypted``/``api_key_last4`` of ``None`` keep the saved key.
    """
    config = get_config(db, user_id)
    if config is None:
        config = UserAIProviderConfig(user_id=user_id)
        db.add(config)
    config.provider = provider
    config.model_id = model_id
    config.is_active = True
    if api_key_encrypted is not None:
        config.api_key_encrypted = api_key_encrypted
        config.api_key_last4 = api_key_last4 or ""
    db.commit()
    db.refresh(config)
    return config


def delete_config(db: Session, user_id: int) -> bool:
    """Delete the user's configuration; return whether one existed."""
    config = get_config(db, user_id)
    if config is None:
        return False
    db.delete(config)
    db.commit()
    return True
