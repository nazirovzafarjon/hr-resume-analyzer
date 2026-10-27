"""Unit tests for password hashing and JWT helpers (``app.core.security``)."""

from datetime import datetime, timedelta, timezone

import pytest
from jose import JWTError, jwt

from app.core.config import settings
from app.core.security import (
    TOKEN_PURPOSE_ACCESS,
    TOKEN_PURPOSE_REFRESH,
    TOKEN_PURPOSE_RESET,
    create_access_token,
    create_password_reset_token,
    create_refresh_token,
    decode_access_token,
    decode_reset_token,
    decode_token_for_purpose,
    hash_password,
    token_expires_at,
    token_id,
    token_issued_at,
    token_purpose,
    verify_password,
)


class TestPasswordHashing:
    """bcrypt hashing always stores a salted digest, never the plain password."""

    def test_hash_password_returns_bcrypt_string(self):
        hashed = hash_password("SuperSecret123")
        assert isinstance(hashed, str)
        assert hashed.startswith("$2b$")

    def test_hash_password_uses_a_fresh_salt_every_time(self):
        assert hash_password("same-password") != hash_password("same-password")

    def test_verify_password_accepts_correct_password(self):
        hashed = hash_password("SuperSecret123")
        assert verify_password("SuperSecret123", hashed) is True

    def test_verify_password_rejects_wrong_password(self):
        hashed = hash_password("SuperSecret123")
        assert verify_password("wrong-password", hashed) is False

    def test_verify_password_rejects_malformed_hash(self):
        # A corrupt/stale hash must not crash the login flow.
        assert verify_password("SuperSecret123", "not-a-bcrypt-hash") is False

    def test_verify_password_rejects_missing_hash(self):
        # Google-only accounts have no hash; verification must never raise.
        assert verify_password("SuperSecret123", None) is False

    def test_passwords_longer_than_72_bytes_are_truncated(self):
        # bcrypt only reads the first 72 bytes; a suffix beyond that is ignored.
        hashed = hash_password("a" * 100)
        assert verify_password("a" * 72 + "DIFFERENT-SUFFIX", hashed) is True


class TestJwt:
    """JWT creation and validation."""

    def test_create_access_token_returns_signed_token(self):
        token = create_access_token(subject=1)
        assert isinstance(token, str)
        assert token.count(".") == 2

    def test_decode_returns_subject_and_expiry(self):
        token = create_access_token(subject=42)
        payload = decode_access_token(token)
        assert payload["sub"] == "42"
        assert "exp" in payload

    def test_decode_rejects_garbage_token(self):
        with pytest.raises(JWTError):
            decode_access_token("this.is.not.a.jwt")

    def test_decode_rejects_token_signed_with_another_secret(self):
        token = jwt.encode({"sub": "1", "exp": 9999999999}, "another-secret", algorithm="HS256")
        with pytest.raises(JWTError):
            decode_access_token(token)

    def test_decode_rejects_tampered_token(self):
        token = create_access_token(subject=1)
        tampered = token[:-4] + "abcd"
        with pytest.raises(JWTError):
            decode_access_token(tampered)

    def test_decode_rejects_expired_token(self):
        token = create_access_token(subject=1, expires_delta=timedelta(minutes=-10))
        with pytest.raises(JWTError):
            decode_access_token(token)


class TestTokenPurposes:
    """Access / refresh / password-reset tokens are not interchangeable."""

    def test_access_token_is_tagged_access(self):
        payload = decode_access_token(create_access_token(subject=7))
        assert token_purpose(payload) == TOKEN_PURPOSE_ACCESS

    def test_legacy_token_without_a_type_claim_counts_as_access(self):
        # Tokens minted before `typ` existed must keep authenticating sessions.
        legacy = jwt.encode(
            {"sub": "7", "exp": datetime.now(timezone.utc) + timedelta(minutes=5)},
            settings.SECRET_KEY,
            algorithm=settings.ALGORITHM,
        )
        assert token_purpose(decode_access_token(legacy)) == TOKEN_PURPOSE_ACCESS

    def test_refresh_token_is_tagged_refresh(self):
        payload = decode_access_token(create_refresh_token(subject=7))
        assert token_purpose(payload) == TOKEN_PURPOSE_REFRESH

    def test_reset_token_is_tagged_password_reset(self):
        payload = decode_access_token(create_password_reset_token(subject=7))
        assert token_purpose(payload) == TOKEN_PURPOSE_RESET

    def test_refresh_token_defaults_to_a_long_lifetime(self):
        payload = decode_access_token(create_refresh_token(subject=7))
        lifetime = token_expires_at(payload) - token_issued_at(payload)
        assert lifetime > timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS - 1)

    def test_reset_token_defaults_to_a_short_lifetime(self):
        payload = decode_access_token(create_password_reset_token(subject=7))
        lifetime = token_expires_at(payload) - token_issued_at(payload)
        assert lifetime <= timedelta(minutes=settings.PASSWORD_RESET_TOKEN_EXPIRE_MINUTES)

    def test_decode_for_purpose_accepts_matching_token(self):
        token = create_refresh_token(subject=3)
        assert decode_token_for_purpose(token, TOKEN_PURPOSE_REFRESH)["sub"] == "3"

    def test_decode_for_purpose_rejects_other_purposes(self):
        with pytest.raises(JWTError):
            decode_token_for_purpose(create_access_token(subject=3), TOKEN_PURPOSE_REFRESH)
        with pytest.raises(JWTError):
            decode_token_for_purpose(
                create_password_reset_token(subject=3), TOKEN_PURPOSE_REFRESH
            )

    def test_reset_credential_accepts_reset_and_access_only(self):
        assert decode_reset_token(create_password_reset_token(subject=3))["sub"] == "3"
        assert decode_reset_token(create_access_token(subject=3))["sub"] == "3"
        with pytest.raises(JWTError):
            decode_reset_token(create_refresh_token(subject=3))

    def test_every_token_gets_a_unique_id(self):
        first = decode_access_token(create_refresh_token(subject=3))
        second = decode_access_token(create_refresh_token(subject=3))
        assert token_id(first) and token_id(first) != token_id(second)

    def test_timestamp_claims_are_aware_datetimes(self):
        payload = decode_access_token(create_access_token(subject=3))
        assert token_issued_at(payload).tzinfo is not None
        assert token_expires_at(payload) > token_issued_at(payload)

    def test_timestamp_claims_tolerate_missing_or_broken_values(self):
        assert token_issued_at({}) is None
        assert token_expires_at({"exp": "not-a-number"}) is None
        assert token_id({}) is None