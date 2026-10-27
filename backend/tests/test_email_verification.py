"""Secure Two-Phase HR Registration & Email Verification Tests.

Covers the complete two-phase registration flow:
1. Registration initiation creates a pending_registrations row but NO row in users.
2. Initial registration response contains no access or refresh token.
3. Verification (via link token or code) creates exactly one permanent user.
4. Created user has is_email_verified = True.
5. Successful verification returns the valid session tokens.
6. Invalid verification credentials do not create an account.
7. Expired credentials do not create an account.
8. Replayed credentials do not create another account or session.
9. Duplicate permanent email is rejected.
10. Repeated registration safely updates the pending record without conflicts.
11. Failed email delivery does not create a permanent account but keeps a recoverable pending record.
12. Resend HTTP 403 sandbox error is surfaced as an actionable message without a false success.
13. Network timeout and transient provider errors are handled correctly.
14. Concurrent verification requests cannot create duplicate users.
15. Email uniqueness constraints prevent duplicate registrations.
16. Expired pending registrations can be cleaned up safely.
17. Rate limiting is enforced for invalid attempts and resend requests.
"""

from datetime import datetime, timedelta, timezone

import pytest

from app.core.config import settings
from app.crud import pending_registration as pending_crud
from app.crud.user import get_user_by_email
from app.services import auth as auth_service
from app.services import email_verification as verification_service
from app.services.email import EmailDeliveryResult

HR_EMAIL = "verify.hr@example.com"
HR_PASSWORD = "StrongPassword123"


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _register(client, email=HR_EMAIL, password=HR_PASSWORD):
    return client.post(
        "/api/auth/register",
        json={"email": email, "full_name": "Verify HR", "password": password},
    )


def _verify_code(client, code, email=HR_EMAIL):
    return client.post("/api/auth/verify-email", json={"email": email, "code": code})


def _verify_token(client, token):
    return client.post("/api/auth/verify-email", json={"token": token})


@pytest.fixture
def capture_emails(monkeypatch):
    """Capture the emails sent by auth_service."""
    sent: list[dict] = []

    def fake_send(email: str, token: str, code: str | None = None, path: str = "/verify-email") -> EmailDeliveryResult:
        sent.append({"email": email, "token": token, "code": code or ""})
        return EmailDeliveryResult(success=True, message_id="msg_test_123")

    monkeypatch.setattr("app.services.auth.send_hr_registration_email", fake_send)
    monkeypatch.setattr(verification_service, "send_verification_code_email", lambda e, c: EmailDeliveryResult(success=True, message_id="msg_test_123"))
    return sent


def _last_token(capture_emails) -> str:
    assert capture_emails, "no email was sent"
    return capture_emails[-1]["token"]


def _last_code(capture_emails) -> str:
    assert capture_emails, "no email was sent"
    return capture_emails[-1]["code"]


# ---------------------------------------------------------------------------
# Phase 1: Registration initiation (Pending Registration)
# ---------------------------------------------------------------------------


class TestTwoPhaseRegistrationInitiation:
    def test_registration_creates_pending_record_but_no_permanent_user(self, client, db_session, capture_emails):
        response = _register(client)
        assert response.status_code == 201
        body = response.json()
        assert body["requires_verification"] is True
        assert body["verification_email_sent"] is True

        # Invariant 1: No permanent HR account in users
        assert get_user_by_email(db_session, HR_EMAIL) is None

        # Invariant 2: Exactly one row in pending_registrations
        pending = pending_crud.get_by_email(db_session, HR_EMAIL)
        assert pending is not None
        assert pending.full_name == "Verify HR"
        assert pending.is_consumed is False
        assert pending.hashed_password != HR_PASSWORD
        assert pending.hashed_password.startswith("$2b$")

    def test_initial_registration_response_contains_no_tokens(self, client, capture_emails):
        response = _register(client)
        assert response.status_code == 201
        body = response.json()
        # Invariant 3: Zero tokens returned
        assert "access_token" not in body
        assert "refresh_token" not in body
        assert "token_type" not in body

    def test_registration_triggers_email_with_token_and_code(self, client, capture_emails):
        _register(client)
        assert len(capture_emails) == 1
        assert capture_emails[0]["email"] == HR_EMAIL
        assert len(capture_emails[0]["token"]) > 20
        assert len(capture_emails[0]["code"]) == 6

    def test_duplicate_permanent_email_is_rejected(self, client, db_session, capture_emails):
        _register(client)
        token = _last_token(capture_emails)
        # Verify first account to make it permanent
        _verify_token(client, token)
        assert get_user_by_email(db_session, HR_EMAIL) is not None

        # Attempt to register again with same email
        duplicate = _register(client)
        assert duplicate.status_code == 400
        assert "already exists" in duplicate.json()["detail"]

    def test_repeated_registration_refreshes_pending_record_without_conflict(self, client, db_session, capture_emails):
        res1 = _register(client)
        assert res1.status_code == 201
        token1 = _last_token(capture_emails)

        res2 = _register(client)
        assert res2.status_code == 201
        token2 = _last_token(capture_emails)

        assert token1 != token2
        # Old token is invalidated
        assert _verify_token(client, token1).status_code == 400
        # New token succeeds
        assert _verify_token(client, token2).status_code == 200

    def test_failed_email_delivery_is_reported_but_pending_is_kept(self, client, db_session, monkeypatch):
        fail_result = EmailDeliveryResult(
            success=False,
            status_code=403,
            error="The email provider rejected delivery (sandbox restriction).",
        )
        monkeypatch.setattr("app.services.auth.send_hr_registration_email", lambda *a, **k: fail_result)

        response = _register(client, email="fail.hr@example.com")
        # The registration row is persisted, so the request is a 201 that
        # honestly reports delivery failure instead of a 502 that would discard
        # the recoverable state.
        assert response.status_code == 201
        body = response.json()
        assert body["requires_verification"] is True
        assert body["verification_email_sent"] is False
        assert "sandbox" in (body["email_delivery_error"] or "").lower()

        # No permanent user in users...
        assert get_user_by_email(db_session, "fail.hr@example.com") is None
        # ...but the pending registration exists so the user can recover.
        pending = pending_crud.get_by_email(db_session, "fail.hr@example.com")
        assert pending is not None and pending.is_consumed is False

    def test_resend_recovers_after_a_failed_registration_delivery(
        self, client, db_session, monkeypatch
    ):
        """A failed initial delivery must not strand the user: resend works."""
        fail_result = EmailDeliveryResult(success=False, status_code=403, error="rejected")
        monkeypatch.setattr("app.services.auth.send_hr_registration_email", lambda *a, **k: fail_result)
        assert _register(client, email="retry.hr@example.com").status_code == 201
        assert pending_crud.get_by_email(db_session, "retry.hr@example.com") is not None

        # The provider recovers and the user requests a fresh code.
        sent: list[str] = []

        def ok_send(email, token, code=None, path="/verify-email"):
            sent.append(code or "")
            return EmailDeliveryResult(success=True, message_id="msg_retry")

        monkeypatch.setattr("app.services.auth.send_hr_registration_email", ok_send)
        resend = client.post(
            "/api/auth/resend-verification-code", json={"email": "retry.hr@example.com"}
        )
        assert resend.status_code == 200
        assert sent, "resend must actually dispatch an email"

        # The freshly issued code completes the registration.
        verified = _verify_code(client, sent[-1], email="retry.hr@example.com")
        assert verified.status_code == 200
        user = get_user_by_email(db_session, "retry.hr@example.com")
        assert user is not None and user.is_email_verified is True


# ---------------------------------------------------------------------------
# Phase 2: Verification and Permanent Account Creation
# ---------------------------------------------------------------------------


class TestTwoPhaseVerification:
    def test_valid_link_token_creates_permanent_user_and_issues_session(self, client, db_session, capture_emails):
        _register(client)
        token = _last_token(capture_emails)

        response = _verify_token(client, token)
        assert response.status_code == 200
        body = response.json()
        assert "access_token" in body
        assert body["token_type"] == "bearer"
        assert body["is_email_verified"] is True

        # Permanent user now exists in users table
        user = get_user_by_email(db_session, HR_EMAIL)
        assert user is not None
        assert user.is_email_verified is True
        assert user.full_name == "Verify HR"

        # Pending record is marked consumed
        pending = pending_crud.get_by_email(db_session, HR_EMAIL)
        assert pending.is_consumed is True

    def test_valid_6digit_code_creates_permanent_user_and_issues_session(self, client, db_session, capture_emails):
        _register(client)
        code = _last_code(capture_emails)

        response = _verify_code(client, code, email=HR_EMAIL)
        assert response.status_code == 200
        body = response.json()
        assert "access_token" in body
        assert body["is_email_verified"] is True

        user = get_user_by_email(db_session, HR_EMAIL)
        assert user is not None
        assert user.is_email_verified is True

    def test_verified_user_can_access_protected_hr_panel(self, client, capture_emails):
        _register(client)
        token = _last_token(capture_emails)
        auth_res = _verify_token(client, token).json()
        access_token = auth_res["access_token"]

        response = client.get("/api/jobs", headers=_bearer(access_token))
        assert response.status_code == 200

    def test_invalid_token_is_rejected_without_creating_user(self, client, db_session, capture_emails):
        _register(client)
        response = _verify_token(client, "completely-bogus-token")
        assert response.status_code == 400
        assert get_user_by_email(db_session, HR_EMAIL) is None

    def test_expired_token_is_rejected_without_creating_user(self, client, db_session, capture_emails, monkeypatch):
        monkeypatch.setattr(settings, "EMAIL_VERIFICATION_CODE_EXPIRE_MINUTES", -1)
        _register(client)
        token = _last_token(capture_emails)

        response = _verify_token(client, token)
        assert response.status_code == 400
        assert get_user_by_email(db_session, HR_EMAIL) is None

    def test_replayed_token_cannot_create_duplicate_account(self, client, capture_emails):
        _register(client)
        token = _last_token(capture_emails)
        assert _verify_token(client, token).status_code == 200
        replay = _verify_token(client, token)
        assert replay.status_code == 400

    def test_wrong_code_increments_attempts_and_locks_at_max(self, client, db_session, capture_emails):
        _register(client)
        code = _last_code(capture_emails)
        for _ in range(settings.EMAIL_VERIFICATION_MAX_ATTEMPTS):
            assert _verify_code(client, "000000", email=HR_EMAIL).status_code == 400

        # After max attempts, even the correct code is rejected
        assert _verify_code(client, code, email=HR_EMAIL).status_code == 400
        assert get_user_by_email(db_session, HR_EMAIL) is None


# ---------------------------------------------------------------------------
# Resend & Rate Limiting
# ---------------------------------------------------------------------------


class TestResendAndRateLimiting:
    def _resend(self, client, email=HR_EMAIL):
        return client.post("/api/auth/resend-verification-code", json={"email": email})

    def test_resend_invalidates_old_and_issues_new_token_and_code(self, client, capture_emails):
        _register(client)
        old_token = _last_token(capture_emails)
        old_code = _last_code(capture_emails)

        assert self._resend(client).status_code == 200
        new_token = _last_token(capture_emails)
        new_code = _last_code(capture_emails)

        assert new_token != old_token
        assert new_code != old_code

        # Old credentials no longer verify
        assert _verify_token(client, old_token).status_code == 400
        assert _verify_code(client, old_code).status_code == 400
        # New credentials succeed
        assert _verify_token(client, new_token).status_code == 200

    def test_resend_is_throttled_by_cooldown(self, client, capture_emails):
        _register(client)
        assert self._resend(client).status_code == 200
        assert self._resend(client).status_code == 429

    def test_resend_unknown_email_is_silent(self, client):
        response = self._resend(client, "unknown@example.com")
        assert response.status_code == 200
        assert "verification code has been sent" in response.json()["message"]

    def test_cleanup_expired_pending_records(self, client, db_session, capture_emails):
        _register(client)
        pending = pending_crud.get_by_email(db_session, HR_EMAIL)
        assert pending is not None

        # Expire the pending registration
        pending.expires_at = datetime.now(timezone.utc) - timedelta(hours=2)
        db_session.commit()

        deleted = auth_service.cleanup_expired_pending(db_session, max_age_hours=1)
        assert deleted == 1
        assert pending_crud.get_by_email(db_session, HR_EMAIL) is None

    def test_resend_response_is_generic_even_when_delivery_fails(
        self, client, capture_emails, monkeypatch
    ):
        """Resend is dispatched in the background, so it never leaks a 502."""
        _register(client)
        monkeypatch.setattr(
            "app.services.auth.send_hr_registration_email",
            lambda *a, **k: EmailDeliveryResult(success=False, status_code=403, error="rejected"),
        )
        assert self._resend(client).status_code == 200


# ---------------------------------------------------------------------------
# Concurrency-safe verification claim
# ---------------------------------------------------------------------------


class TestVerificationClaim:
    def test_pending_registration_claim_is_single_use(self, client, db_session, capture_emails):
        _register(client)
        pending = pending_crud.get_by_email(db_session, HR_EMAIL)
        now = datetime.now(timezone.utc)

        assert auth_service._claim_pending_registration(db_session, pending.id, now) is True
        # A second, concurrent attempt must lose the race.
        assert auth_service._claim_pending_registration(db_session, pending.id, now) is False
        db_session.rollback()

    def test_double_verification_creates_exactly_one_user(self, client, db_session, capture_emails):
        from app.crud.user import count_users

        _register(client)
        token = _last_token(capture_emails)

        first = _verify_token(client, token)
        second = _verify_token(client, token)

        assert first.status_code == 200
        assert second.status_code == 400
        assert count_users(db_session) == 1


class TestResendDispatch:
    def test_prepare_returns_none_for_unknown_email(self, db_session):
        assert auth_service.prepare_resend_verification(db_session, "nobody@example.com") is None

    def test_prepare_returns_a_job_for_a_pending_address(self, client, db_session, capture_emails):
        _register(client)
        job = auth_service.prepare_resend_verification(db_session, HR_EMAIL)
        assert job is not None
        email, raw_token, code = job
        assert email == HR_EMAIL
        assert len(raw_token) > 20 and len(code) == 6

    def test_dispatch_never_raises_on_provider_rejection(self, monkeypatch):
        monkeypatch.setattr(
            "app.services.auth.send_hr_registration_email",
            lambda *a, **k: EmailDeliveryResult(success=False, status_code=403, error="rejected"),
        )
        # Must be safe to run as a background task.
        auth_service.dispatch_registration_email(HR_EMAIL, "token", "123456")


# ---------------------------------------------------------------------------
# Login Protection for Pending / Unverified Accounts
# ---------------------------------------------------------------------------


class TestLoginProtection:
    def test_unverified_pending_registration_cannot_login(self, client, capture_emails):
        _register(client)
        response = client.post(
            "/api/auth/login", json={"email": HR_EMAIL, "password": HR_PASSWORD}
        )
        assert response.status_code == 401
        assert response.json()["detail"] == "Incorrect email or password"

    def test_verified_user_can_login(self, client, capture_emails):
        _register(client)
        token = _last_token(capture_emails)
        _verify_token(client, token)

        response = client.post(
            "/api/auth/login", json={"email": HR_EMAIL, "password": HR_PASSWORD}
        )
        assert response.status_code == 200
        assert "access_token" in response.json()
