"""Application-wide, machine-readable error signals.

Currently a single case: an authenticated account whose email is not verified
trying to use its HR or Candidate panel. The guards raise
:class:`EmailVerificationRequiredError` and ``app.main`` renders it as::

    HTTP 403
    {"detail": "Email verification is required to continue.",
     "code": "EMAIL_VERIFICATION_REQUIRED"}

The ``code`` lets the frontend show the "verify your email" UI instead of a
generic "Forbidden" message.
"""

from __future__ import annotations

#: Machine-readable code returned with the 403 (see module docstring).
EMAIL_VERIFICATION_REQUIRED = "EMAIL_VERIFICATION_REQUIRED"

EMAIL_VERIFICATION_REQUIRED_MESSAGE = "Email verification is required to continue."


class EmailVerificationRequiredError(Exception):
    """An unverified account tried to create/use a panel (-> 403)."""

    code = EMAIL_VERIFICATION_REQUIRED

    def __init__(self, message: str | None = None) -> None:
        super().__init__(message or EMAIL_VERIFICATION_REQUIRED_MESSAGE)
