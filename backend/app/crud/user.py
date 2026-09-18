from typing import Any

import logging

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.user import User
from app.schemas.user import UserCreate

logger = logging.getLogger(__name__)


def create_user(db: Session, payload: UserCreate, is_superuser: bool = False) -> User:
    # Create and return a new user with a hashed password.
    # Raises ValueError on duplicate email.

    user = User(
        email=payload.email,
        full_name=payload.full_name,
        hashed_password=hash_password(payload.password),
        is_superuser=is_superuser,
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ValueError("A user with this email already exists") from exc
    db.refresh(user)
    return user


def list_users(db: Session, skip: int = 0, limit: int = 100) -> list[User]:
    # Return users ordered by id, honoring pagination bounds.


    return (
        db.query(User)
        .order_by(User.id)
        .offset(skip)
        .limit(limit)
        .all()
    )


def has_superuser(db: Session) -> bool:
    # Return True when at least one superuser exists.



    first = db.query(User.id).filter(User.is_superuser.is_(True)).first()
    return first is not None


def get_user_by_id(db: Session, user_id: int) -> User | None:
    # Return the user with the given id, or None if it does not exist.#


    return db.get(User, user_id)


def get_user_by_email(db: Session, email: str) -> User | None:
    # Return the user with the given email, or None if it does not exist.#


    return db.query(User).filter(User.email == email).first()


def get_user_by_google_id(db: Session, google_id: str) -> User | None:
    # Return the user linked to the given Google account id, or None.#


    return db.query(User).filter(User.google_id == google_id).first()


def get_or_create_google_user(
    db: Session,
    *,
    google_id: str,
    email: str,
    full_name: str,
    picture: str | None,
) -> User:
    """Resolve (find or create) a user authenticated via Google.

    Lookup strategy:
    * Prefer the Google ``sub`` id — the most robust key.
    * Fall back to the verified email. This lets a user who first registered
      with a password sign in with Google later: the existing record is found
      by email and the ``google_id`` is attached, linking both sign-in paths.
    * If the profile data (name / avatar) changed on Google's side, keep the
      stored columns up to date.

    When no match exists a new account is created (with ``is_active=True`` and
    no password hash) — an unknown Google user is never an error. If a
    concurrent request creates the same account between the SELECT and the
    COMMIT, the lookup is retried and the account linked instead of failing.

    Raises:
        ValueError: Only when a commit-race leaves no resolvable user
            (should not happen in practice since Google verifies email).
    """
    user = get_user_by_google_id(db, google_id)
    if user is None:
        user = get_user_by_email(db, email)

    if user is not None:
        logger.info(
            "Google user lookup: matched id=%s email=%s (by %s)",
            user.id,
            user.email,
            "google_id" if user.google_id == google_id else "email",
        )
        _link_and_refresh_google_profile(db, user, google_id, full_name, picture)
        return user

    logger.info(
        "Google user lookup: no match for email=%s google_id=…%s — creating account",
        email,
        str(google_id)[-6:] if google_id else "<none>",
    )
    user = User(
        email=email,
        full_name=full_name,
        picture=picture,
        google_id=google_id,
        is_active=True,
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        # Two concurrent sign-ins can pass the SELECT above and both try to
        # INSERT (unique email / google_id). Roll back and re-resolve instead
        # of failing the sign-in the second request belongs to.
        db.rollback()
        logger.warning(
            "Google user creation hit a unique-constraint race; re-resolving %s",
            email,
        )
        user = get_user_by_google_id(db, google_id) or get_user_by_email(db, email)
        if user is None:
            raise ValueError(
                "This Google email is already registered with another account."
            ) from None
        _link_and_refresh_google_profile(db, user, google_id, full_name, picture)
        return user
    db.refresh(user)
    logger.info("Google user creation: created id=%s email=%s", user.id, user.email)
    return user


def _link_and_refresh_google_profile(
    db: Session,
    user: User,
    google_id: str,
    full_name: str,
    picture: str | None,
) -> None:
    """Attach the Google identity and refresh profile columns when they change.

    Handles the "existing account" branch of Google login: a password-based
    user signing in with Google for the first time gets ``google_id`` set
    (linking the accounts), and any profile drift (name/avatar) is synced.
    Only commits when something actually changed.
    """
    changed = False
    if user.google_id is None:
        user.google_id = google_id
        changed = True
    if full_name and user.full_name != full_name:
        user.full_name = full_name
        changed = True
    if picture and user.picture != picture:
        user.picture = picture
        changed = True
    if changed:
        db.commit()
        db.refresh(user)


def update_user(db: Session, user: User, payload: dict[str, Any]) -> User:
    # Apply the submitted updates to a user and return the instance.#


    if "full_name" in payload:
        user.full_name = payload["full_name"]
    if "email" in payload:
        user.email = payload["email"]
    if "hashed_password" in payload:
        user.hashed_password = payload["hashed_password"]
    if "google_id" in payload:
        user.google_id = payload["google_id"]
    if "picture" in payload:
        user.picture = payload["picture"]
    if "profile_image" in payload:
        user.profile_image = payload["profile_image"]
    if "is_active" in payload:
        user.is_active = payload["is_active"]
    if "is_superuser" in payload:
        user.is_superuser = payload["is_superuser"]
    db.commit()
    db.refresh(user)
    return user


def delete_user(db: Session, user: User) -> None:
    # Delete a user record.#


    db.delete(user)
    db.commit()


def count_users(db: Session) -> int:
    # Return the number of registered users.#


    return db.query(func.count(User.id)).scalar() or 0