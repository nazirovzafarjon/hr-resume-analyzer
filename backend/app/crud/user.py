from typing import Any

import logging

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.user import User
from app.schemas.user import UserCreate

logger = logging.getLogger(__name__)


def create_user(
    db: Session,
    payload: UserCreate,
    is_superuser: bool = False,
    is_email_verified: bool = True,
) -> User:
    # Create and return a new user with a hashed password.
    # Raises ValueError on duplicate email.
    #
    # ``is_email_verified`` defaults to True so programmatic creation (the
    # seeded superuser, admin-created accounts) is trusted. The public
    # registration path explicitly passes False.

    user = User(
        email=payload.email.strip().lower(),
        full_name=payload.full_name.strip(),
        hashed_password=hash_password(payload.password),
        is_superuser=is_superuser,
        is_email_verified=is_email_verified,
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


    return (
        db.query(User)
        .filter(func.lower(User.email) == email.strip().lower())
        .first()
    )


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
    """Resolve (find or create) a user authenticated via Google."""
    email = email.strip().lower()
    full_name = full_name.strip()
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
        # Google has already verified this address (enforced by the caller via
        # the email_verified claim), so the account needs no extra step.
        is_email_verified=True,
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
    # Signing in with a (verified) Google address proves the email is real, so
    # linking it satisfies the verification gate too.
    if not user.is_email_verified:
        user.is_email_verified = True
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