/**
 * Thin localStorage wrapper for the JWT pair.
 *
 * Kept as plain functions (not React state) so the non-React API client can
 * read, rotate and clear the tokens without depending on the auth context. The
 * React state in `context/AuthContext` stays in sync by calling these helpers.
 */

const TOKEN_KEY = "resumeAnalyzer.accessToken";
const REFRESH_TOKEN_KEY = "resumeAnalyzer.refreshToken";

/** Return the stored access JWT, or null when the user is not signed in. */
export function getToken(): string | null {
  return window.localStorage.getItem(TOKEN_KEY);
}

/** Return the stored refresh JWT, or null when none was issued. */
export function getRefreshToken(): string | null {
  return window.localStorage.getItem(REFRESH_TOKEN_KEY);
}

/**
 * Persist a whole token pair after login, registration, Google sign-in or a
 * password reset / skip.
 *
 * `refreshToken` is optional: an older backend (or a response without one)
 * clears the stored refresh token instead of leaving a stale credential behind.
 */
export function saveTokens(accessToken: string, refreshToken?: string | null): void {
  window.localStorage.setItem(TOKEN_KEY, accessToken);
  if (refreshToken) {
    window.localStorage.setItem(REFRESH_TOKEN_KEY, refreshToken);
  } else {
    window.localStorage.removeItem(REFRESH_TOKEN_KEY);
  }
}

/** Remove the stored JWTs (logout or an unrecoverable expired session). */
export function clearToken(): void {
  window.localStorage.removeItem(TOKEN_KEY);
  window.localStorage.removeItem(REFRESH_TOKEN_KEY);
}