/**
 * Shared client-side validation helpers for the authentication forms.
 *
 * These rules intentionally mirror the backend's actual validation
 * (see `backend/app/schemas/auth.py` and `backend/app/core/security.py`).
 * No stricter password policy is invented here on purpose.
 */

/** bcrypt (used by the backend) only hashes the first 72 bytes of a password. */
export const PASSWORD_MAX_LENGTH = 72;

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

/** Returns true when the value looks like a reasonable email address. */
export function isValidEmail(email: string): boolean {
  return EMAIL_PATTERN.test(email.trim());
}

/** Returns an error message for a chosen password, or null when it is valid. */
export function getPasswordError(password: string): string | null {
  if (!password) {
    return "Password is required.";
  }
  if (password.length > PASSWORD_MAX_LENGTH) {
    return `Password must be at most ${PASSWORD_MAX_LENGTH} characters.`;
  }
  return null;
}
