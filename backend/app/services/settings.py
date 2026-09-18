"""Profile settings business logic (the authenticated user's own account).

Owns the self-service profile operations behind the Settings page: updating
name/email and managing the profile image. Every function works on the
``User`` supplied by ``get_current_user`` — never on a client-supplied id —
so a user can only ever modify their own account. Password changes live in
``app.services.auth`` because they are part of the authentication flow
(token re-issuing / session revocation).

Low-level storage writes (file bytes) happen here, database access goes
through ``app.crud.user``.
"""

import logging
from pathlib import Path
from uuid import uuid4

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.crud import user as user_crud
from app.models.user import User
from app.schemas.user import UserProfileUpdate

logger = logging.getLogger(__name__)

# Supported profile-image formats: detected MIME type -> file extension.
_ALLOWED_IMAGE_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}

# Sub-directory (inside UPLOAD_DIR) that profile images are stored in.
_PROFILE_IMAGES_DIR = "profile"


def update_profile(db: Session, user: User, payload: UserProfileUpdate) -> User:
    """Apply the submitted name/email changes to the current user.

    Only fields the client actually sent are changed; the schema has already
    trimmed ``full_name`` and normalized ``email`` (``EmailStr`` lowercases).
    A new email must not already belong to another account.

    Raises:
        ValueError: If the email is already used by a different account.
    """
    data = payload.model_dump(exclude_unset=True)
    if not data:
        return user

    email = data.get("email")
    if email is not None:
        owner = user_crud.get_user_by_email(db, email)
        if owner is not None and owner.id != user.id:
            raise ValueError("A user with this email already exists")

    try:
        return user_crud.update_user(
            db, user, {key: data[key] for key in ("full_name", "email") if key in data}
        )
    except IntegrityError as exc:
        # Two concurrent requests can both pass the SELECT above and race on the
        # unique email constraint; roll back and report the duplicate cleanly.
        db.rollback()
        raise ValueError("A user with this email already exists") from exc


def save_profile_image(
    db: Session,
    user: User,
    content: bytes,
    *,
    content_type: str | None,
) -> User:
    """Validate, store and attach a new profile image for ``user``.

    Validation never trusts the raw filename or the declared content type
    alone: the file's real content is checked (magic bytes), the declared type
    must be an allowed image MIME type, and the upload must stay under the
    configured size limit. The stored filename is a fresh UUID — the client's
    filename is never used on disk, which also rules out path traversal.

    An existing profile image is replaced (the old file is removed after the
    database commit succeeds).

    Raises:
        ValueError: If the content is too large or not a supported image.
    """
    max_bytes = settings.PROFILE_IMAGE_MAX_SIZE_MB * 1024 * 1024
    if len(content) > max_bytes:
        raise ValueError(
            f"Profile image must be at most {settings.PROFILE_IMAGE_MAX_SIZE_MB} MB"
        )

    detected_type = _detect_image_type(content)
    if detected_type is None:
        raise ValueError("Unsupported file type. Allowed: JPG, PNG, WEBP")
    if content_type and content_type not in _ALLOWED_IMAGE_TYPES:
        raise ValueError("Unsupported file type. Allowed: JPG, PNG, WEBP")
    if content_type and content_type != detected_type:
        raise ValueError("The file content does not match its declared type")

    images_dir = _profile_images_dir()
    images_dir.mkdir(parents=True, exist_ok=True)
    # uuid4().hex always produces a unique, filesystem-safe name.
    stored_name = f"{uuid4().hex}{_ALLOWED_IMAGE_TYPES[detected_type]}"
    (images_dir / stored_name).write_bytes(content)

    old_path = user.profile_image
    user.profile_image = f"/uploads/{_PROFILE_IMAGES_DIR}/{stored_name}"
    db.commit()
    db.refresh(user)

    if old_path:
        _delete_image_file(old_path)
    logger.info("Profile image saved for user id=%s", user.id)
    return user


def remove_profile_image(db: Session, user: User) -> User:
    """Remove the user's profile image (no-op when there is none).

    The database is updated first, then the stored file is deleted best-effort
    so a failed commit never destroys a file the DB row still references.
    """
    old_path = user.profile_image
    if old_path is None:
        return user

    user.profile_image = None
    db.commit()
    db.refresh(user)
    _delete_image_file(old_path)
    logger.info("Profile image removed for user id=%s", user.id)
    return user


def _detect_image_type(content: bytes) -> str | None:
    """Return the image MIME type from the content itself, or ``None``.

    Checking magic bytes (the file's real signature) is what stops someone
    from renaming an executable or a text file to ``.png`` — the content is
    what decides, not the filename.
    """
    if content.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if content.startswith(b"RIFF") and content[8:12] == b"WEBP":
        return "image/webp"
    return None


def _profile_images_dir() -> Path:
    """Absolute path of the directory that holds profile images."""
    return Path(settings.UPLOAD_DIR) / _PROFILE_IMAGES_DIR


def _delete_image_file(image_url: str | None) -> None:
    """Best-effort removal of a stored image file referenced by ``image_url``.

    The URL is always server-generated (``/uploads/profile/<uuid>.ext``), and
    only its basename is ever joined onto the images directory, so no value can
    escape that folder.
    """
    if not image_url:
        return
    try:
        name = Path(image_url).name
        (Path(settings.UPLOAD_DIR) / _PROFILE_IMAGES_DIR / name).unlink(
            missing_ok=True
        )
    except OSError:
        logger.warning("Could not delete profile image file %r", image_url)