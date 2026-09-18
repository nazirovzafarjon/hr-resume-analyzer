"""Tests for the authenticated user's own profile (Settings) endpoints.

Covers:
* GET /api/auth/me
* PATCH /api/auth/me
* PATCH /api/auth/me/password
* POST /api/auth/me/profile-image and DELETE /api/auth/me/profile-image

Ownership is guaranteed by construction (the user always comes from the JWT),
so the tests also prove that another user's account is never touched.
"""

from io import BytesIO
from pathlib import Path

from app.core.config import settings
from app.core.security import create_access_token, verify_password
from app.crud.user import get_user_by_email
from app.models.user import User

# Minimal-but-real image payloads: valid magic bytes plus filler.
PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"0" * 64
JPEG_BYTES = b"\xff\xd8\xff\xe0" + b"0" * 64
WEBP_BYTES = b"RIFF\x24\x00\x00\x00WEBPVP8 " + b"0" * 64
TEXT_BYTES = b"this is definitely not an image"

PASSWORD = "StrongPassword123"
NEW_PASSWORD = "BrandNewPassword123"


def _login(client, email, password=PASSWORD):
    return client.post("/api/auth/login", json={"email": email, "password": password})


def _upload_image(client, headers, content, filename="avatar.png", content_type="image/png"):
    """POST a profile image with the given content/type under a chosen filename."""
    return client.post(
        "/api/auth/me/profile-image",
        files={"file": (filename, BytesIO(content), content_type)},
        headers=headers,
    )


def _uploaded_path(profile_image_url):
    """Absolute filesystem path of a stored image, from its /uploads URL."""
    return Path(settings.UPLOAD_DIR) / "profile" / Path(profile_image_url).name


# ---------------------------------------------------------------------------
# GET /api/auth/me
# ---------------------------------------------------------------------------


class TestGetMe:
    def test_authenticated_user_gets_own_profile(self, client, user):
        response = client.get("/api/auth/me", headers=user["headers"])
        assert response.status_code == 200
        body = response.json()
        assert body["id"] == user["id"]
        assert body["email"] == user["email"]
        assert body["full_name"] == "HR User"
        assert body["profile_image"] is None
        assert body["has_password"] is True
        # Security data must never leak.
        assert "hashed_password" not in body

    def test_unauthenticated_request_rejected(self, client):
        assert client.get("/api/auth/me").status_code == 401


# ---------------------------------------------------------------------------
# PATCH /api/auth/me
# ---------------------------------------------------------------------------


class TestUpdateMe:
    def test_update_full_name(self, client, user):
        response = client.patch(
            "/api/auth/me", json={"full_name": "John Smith"}, headers=user["headers"]
        )
        assert response.status_code == 200
        body = response.json()
        assert body["full_name"] == "John Smith"
        assert body["email"] == user["email"]  # untouched

    def test_full_name_is_trimmed(self, client, user):
        response = client.patch(
            "/api/auth/me", json={"full_name": "  John Smith  "}, headers=user["headers"]
        )
        assert response.status_code == 200
        assert response.json()["full_name"] == "John Smith"

    def test_update_email(self, client, user):
        response = client.patch(
            "/api/auth/me", json={"email": "renamed@example.com"}, headers=user["headers"]
        )
        assert response.status_code == 200
        assert response.json()["email"] == "renamed@example.com"

    def test_email_normalization_matches_the_auth_flow(self, client, user):
        # EmailStr (used by register/login too) lowercases the domain; the
        # local part keeps its case, so this is the same normalization the
        # rest of the app applies.
        response = client.patch(
            "/api/auth/me", json={"email": "Mixed.Case@Example.COM"}, headers=user["headers"]
        )
        assert response.status_code == 200
        assert response.json()["email"] == "Mixed.Case@example.com"

    def test_update_both_fields(self, client, user):
        response = client.patch(
            "/api/auth/me",
            json={"full_name": "John Smith", "email": "john.smith@example.com"},
            headers=user["headers"],
        )
        assert response.status_code == 200
        body = response.json()
        assert body["full_name"] == "John Smith"
        assert body["email"] == "john.smith@example.com"

    def test_empty_body_is_a_no_op(self, client, user):
        response = client.patch("/api/auth/me", json={}, headers=user["headers"])
        assert response.status_code == 200
        assert response.json()["full_name"] == "HR User"
        assert response.json()["email"] == user["email"]

    def test_empty_name_rejected(self, client, user):
        response = client.patch(
            "/api/auth/me", json={"full_name": ""}, headers=user["headers"]
        )
        assert response.status_code == 422

    def test_whitespace_only_name_rejected(self, client, user):
        response = client.patch(
            "/api/auth/me", json={"full_name": "   "}, headers=user["headers"]
        )
        assert response.status_code == 422

    def test_invalid_email_rejected(self, client, user):
        response = client.patch(
            "/api/auth/me", json={"email": "not-an-email"}, headers=user["headers"]
        )
        assert response.status_code == 422

    def test_duplicate_email_rejected(self, client, user, other_user):
        response = client.patch(
            "/api/auth/me", json={"email": other_user["email"]}, headers=user["headers"]
        )
        assert response.status_code == 400
        assert "already exists" in response.json()["detail"]

    def test_keeping_own_email_is_allowed(self, client, user):
        response = client.patch(
            "/api/auth/me", json={"email": user["email"]}, headers=user["headers"]
        )
        assert response.status_code == 200
        assert response.json()["email"] == user["email"]

    def test_user_stays_authenticated_and_can_login_with_new_email(self, client, user):
        response = client.patch(
            "/api/auth/me", json={"email": "renamed@example.com"}, headers=user["headers"]
        )
        assert response.status_code == 200
        # The existing token keeps working (the JWT only carries the user id).
        assert client.get("/api/auth/me", headers=user["headers"]).status_code == 200
        # Login with the new email + the unchanged password works; the old email
        # no longer does.
        assert _login(client, "renamed@example.com").status_code == 200
        assert _login(client, user["email"]).status_code == 401

    def test_email_change_does_not_touch_the_password(self, client, user, db_session):
        before = get_user_by_email(db_session, user["email"])
        response = client.patch(
            "/api/auth/me", json={"email": "renamed@example.com"}, headers=user["headers"]
        )
        assert response.status_code == 200
        # Re-read from the database (the session caches the earlier object).
        db_session.expire_all()
        after = get_user_by_email(db_session, "renamed@example.com")
        assert after.hashed_password == before.hashed_password
        assert verify_password(PASSWORD, after.hashed_password)

    def test_user_a_cannot_modify_user_b(self, client, user, other_user, db_session):
        # A frontend-supplied user_id is meaningless for this endpoint; only the
        # authenticated user's own row may change.
        response = client.patch(
            "/api/auth/me",
            json={"full_name": "Hacked Name", "user_id": other_user["id"]},
            headers=user["headers"],
        )
        assert response.status_code == 200
        assert response.json()["id"] == user["id"]
        assert response.json()["full_name"] == "Hacked Name"  # A updated

        other = get_user_by_email(db_session, other_user["email"])
        assert other.full_name == "Other HR"  # B untouched
        assert get_user_by_email(db_session, user["email"]) is not None  # A row intact
# ---------------------------------------------------------------------------
# Profile image
# ---------------------------------------------------------------------------


class TestProfileImage:
    def test_upload_succeeds_and_is_served(self, client, user):
        response = _upload_image(client, user["headers"], PNG_BYTES)
        assert response.status_code == 200
        url = response.json()["profile_image"]
        assert url.startswith("/uploads/profile/")
        assert url.endswith(".png")
        # The stored file is actually served back to browsers.
        assert client.get(url).status_code == 200
        # And reflected in the current profile.
        profile = client.get("/api/auth/me", headers=user["headers"]).json()
        assert profile["profile_image"] == url

    def test_jpeg_and_webp_are_accepted(self, client, user):
        jpeg = _upload_image(
            client, user["headers"], JPEG_BYTES, "photo.jpg", "image/jpeg"
        )
        assert jpeg.status_code == 200
        assert jpeg.json()["profile_image"].endswith(".jpg")

        webp = _upload_image(
            client, user["headers"], WEBP_BYTES, "photo.webp", "image/webp"
        )
        assert webp.status_code == 200
        assert webp.json()["profile_image"].endswith(".webp")

    def test_text_content_rejected_even_with_image_name(self, client, user):
        # A .png filename and declared type are not enough — the content decides.
        response = _upload_image(client, user["headers"], TEXT_BYTES)
        assert response.status_code == 400
        assert "Unsupported file type" in response.json()["detail"]

    def test_disallowed_declared_type_rejected(self, client, user):
        # Valid PNG content declared as a GIF must be rejected too.
        response = _upload_image(
            client, user["headers"], PNG_BYTES, "avatar.gif", "image/gif"
        )
        assert response.status_code == 400

    def test_declared_type_mismatch_rejected(self, client, user):
        response = _upload_image(
            client, user["headers"], PNG_BYTES, "avatar.jpg", "image/jpeg"
        )
        assert response.status_code == 400
        assert "does not match" in response.json()["detail"]

    def test_oversized_upload_rejected(self, client, user):
        big = b"\x89PNG\r\n\x1a\n" + b"0" * (6 * 1024 * 1024)  # > 5 MB
        response = _upload_image(client, user["headers"], big)
        assert response.status_code == 400
        assert "at most 5 MB" in response.json()["detail"]

    def test_upload_replaces_image_and_deletes_old_file(self, client, user):
        first_url = _upload_image(client, user["headers"], PNG_BYTES).json()[
            "profile_image"
        ]
        second_url = _upload_image(
            client, user["headers"], JPEG_BYTES, "photo.jpg", "image/jpeg"
        ).json()["profile_image"]

        assert second_url != first_url
        assert _uploaded_path(second_url).exists()
        assert not _uploaded_path(first_url).exists()  # old file cleaned up

    def test_remove_image_works(self, client, user):
        url = _upload_image(client, user["headers"], PNG_BYTES).json()[
            "profile_image"
        ]
        response = client.delete("/api/auth/me/profile-image", headers=user["headers"])
        assert response.status_code == 200
        assert response.json()["profile_image"] is None
        assert client.get("/api/auth/me", headers=user["headers"]).json()[
            "profile_image"
        ] is None
        assert not _uploaded_path(url).exists()  # file removed from disk

    def test_remove_when_no_image_is_safe(self, client, user):
        response = client.delete("/api/auth/me/profile-image", headers=user["headers"])
        assert response.status_code == 200
        assert response.json()["profile_image"] is None

    def test_unauthenticated_upload_rejected(self, client):
        response = _upload_image(client, {}, PNG_BYTES)
        assert response.status_code == 401

    def test_unauthenticated_remove_rejected(self, client):
        assert client.delete("/api/auth/me/profile-image").status_code == 401
# ---------------------------------------------------------------------------
# PATCH /api/auth/me/password
# ---------------------------------------------------------------------------


class TestChangePassword:
    def _change(self, client, headers, current=PASSWORD, new=NEW_PASSWORD):
        return client.patch(
            "/api/auth/me/password",
            json={"current_password": current, "new_password": new},
            headers=headers,
        )

    def test_change_password_returns_fresh_tokens(self, client, user):
        response = self._change(client, user["headers"])
        assert response.status_code == 200
        body = response.json()
        assert body["token_type"] == "bearer"
        assert "access_token" in body
        assert "refresh_token" in body
        # The fresh access token works immediately.
        fresh = {"Authorization": f"Bearer {body['access_token']}"}
        assert client.get("/api/auth/me", headers=fresh).status_code == 200

    def test_old_password_no_longer_works_and_new_one_does(self, client, user):
        self._change(client, user["headers"])
        assert _login(client, user["email"], password=PASSWORD).status_code == 401
        assert _login(client, user["email"], password=NEW_PASSWORD).status_code == 200

    def test_password_hash_is_updated(self, client, user, db_session):
        before = get_user_by_email(db_session, user["email"])
        old_hash = before.hashed_password
        self._change(client, user["headers"])
        # Re-read from the database (the session caches the earlier object).
        db_session.expire_all()
        after = get_user_by_email(db_session, user["email"])
        assert after.hashed_password != old_hash
        assert verify_password(NEW_PASSWORD, after.hashed_password)

    def test_previous_access_token_is_revoked(self, client, user):
        body = self._change(client, user["headers"]).json()
        # The token used to make the change was revoked by it.
        assert client.get("/api/auth/me", headers=user["headers"]).status_code == 401
        fresh = {"Authorization": f"Bearer {body['access_token']}"}
        assert client.get("/api/auth/me", headers=fresh).status_code == 200

    def test_previous_refresh_token_is_revoked(self, client, user):
        old_refresh = _login(client, user["email"]).json()["refresh_token"]
        self._change(client, user["headers"])
        response = client.post(
            "/api/auth/refresh", json={"refresh_token": old_refresh}
        )
        assert response.status_code == 401

    def test_wrong_current_password_rejected(self, client, user):
        response = self._change(client, user["headers"], current="WrongPassword123")
        assert response.status_code == 400
        assert "Current password is incorrect" in response.json()["detail"]
        # And the old password still works (nothing was changed).
        assert _login(client, user["email"], password=PASSWORD).status_code == 200

    def test_empty_new_password_rejected(self, client, user):
        assert self._change(client, user["headers"], new="").status_code == 422

    def test_overlong_new_password_rejected(self, client, user):
        assert self._change(client, user["headers"], new="a" * 73).status_code == 422

    def test_missing_current_password_rejected(self, client, user):
        response = client.patch(
            "/api/auth/me/password",
            json={"new_password": NEW_PASSWORD},
            headers=user["headers"],
        )
        assert response.status_code == 422

    def test_unauthenticated_request_rejected(self, client):
        response = client.patch(
            "/api/auth/me/password",
            json={"current_password": "x", "new_password": "y"},
        )
        assert response.status_code == 401

    def test_google_only_account_cannot_change_password(self, client, db_session):
        # A Google-only account has no local hash to verify against.
        google_user = User(
            email="google@example.com",
            full_name="Google HR",
            hashed_password=None,
            google_id="google-account-1",
            is_active=True,
        )
        db_session.add(google_user)
        db_session.commit()
        headers = {"Authorization": f"Bearer {create_access_token(subject=google_user.id)}"}

        response = self._change(client, headers)
        assert response.status_code == 400
        assert "does not have a password" in response.json()["detail"]

    def test_other_user_password_is_unaffected(self, client, user, other_user):
        self._change(client, user["headers"])
        # User B's credentials are untouched by A's password change.
        assert _login(client, other_user["email"], password=PASSWORD).status_code == 200