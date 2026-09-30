"""Database access for the singleton platform settings row."""

from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.platform_settings import PlatformSettings

#: Primary key of the one and only settings row.
SETTINGS_ROW_ID = 1


def get_or_create(db: Session) -> PlatformSettings:
    """Return the settings row, creating it with defaults on first use."""
    row = db.get(PlatformSettings, SETTINGS_ROW_ID)
    if row is not None:
        return row
    row = PlatformSettings(id=SETTINGS_ROW_ID)
    db.add(row)
    try:
        db.commit()
    except IntegrityError:
        # A concurrent request created it first; use that row.
        db.rollback()
        return db.get(PlatformSettings, SETTINGS_ROW_ID)  # type: ignore[return-value]
    db.refresh(row)
    return row


def update(db: Session, row: PlatformSettings, values: dict[str, Any]) -> PlatformSettings:
    """Apply validated values to the settings row and commit."""
    for key, value in values.items():
        setattr(row, key, value)
    db.commit()
    db.refresh(row)
    return row
