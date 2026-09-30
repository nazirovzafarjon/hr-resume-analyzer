/**
 * Thin localStorage wrapper for the JWT pair.
 *
 * Kept as plain functions (not React state) so the non-React API client can
 * read, rotate and clear the tokens without depending on the auth context. The
 * React state in `context/AuthContext` stays in sync by calling these helpers.
 *
 * Alongside the tokens it maintains a *session hint* cookie for the landing
 * site, which runs on another origin and cannot read this localStorage. The
 * cookie holds no credential — just "1" — and only decides whether the landing
 * shows "Log in / Get started" or "Open workspace". The CRM stays the single
 * judge of whether the session is actually valid.
 */

import { SESSION_COOKIE_DOMAIN } from "../config";

const TOKEN_KEY = "resumeAnalyzer.accessToken";
const REFRESH_TOKEN_KEY = "resumeAnalyzer.refreshToken";

/** Must match SESSION_HINT_COOKIE in landing/src/lib/config.ts. */
const SESSION_HINT_COOKIE = "resumeAnalyzer.signedIn";
/** Matches the backend's default refresh-token lifetime (7 days). */
const SESSION_HINT_MAX_AGE_SECONDS = 7 * 24 * 60 * 60;

function writeSessionHint(signedIn: boolean): void {
  const domain = SESSION_COOKIE_DOMAIN ? `; domain=${SESSION_COOKIE_DOMAIN}` : "";
  const secure = window.location.protocol === "https:" ? "; secure" : "";
  const value = signedIn ? `1; max-age=${SESSION_HINT_MAX_AGE_SECONDS}` : "; max-age=0";
  document.cookie = `${SESSION_HINT_COOKIE}=${value}; path=/; samesite=lax${domain}${secure}`;
}

/**
 * Align the landing-site hint with the stored tokens. Called once on startup
 * so sessions created before the hint existed are picked up too.
 */
export function syncSessionHint(): void {
  writeSessionHint(getToken() !== null);
}

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
  writeSessionHint(true);
}

/** Remove the stored JWTs (logout or an unrecoverable expired session). */
export function clearToken(): void {
  window.localStorage.removeItem(TOKEN_KEY);
  window.localStorage.removeItem(REFRESH_TOKEN_KEY);
  writeSessionHint(false);
}
/*
 * Candidate Portal session.
 *
 * Kept under separate keys so an HR session and a candidate session in the
 * same browser never overwrite each other (they are different identities
 * with different token types; see backend app/models/candidate_account.py).
 * No landing-site hint cookie: the landing links to the portal directly.
 */
const CANDIDATE_TOKEN_KEY = "resumeAnalyzer.candidate.accessToken";
const CANDIDATE_REFRESH_TOKEN_KEY = "resumeAnalyzer.candidate.refreshToken";

export function getCandidateToken(): string | null {
  return window.localStorage.getItem(CANDIDATE_TOKEN_KEY);
}

export function getCandidateRefreshToken(): string | null {
  return window.localStorage.getItem(CANDIDATE_REFRESH_TOKEN_KEY);
}

export function saveCandidateTokens(accessToken: string, refreshToken: string): void {
  window.localStorage.setItem(CANDIDATE_TOKEN_KEY, accessToken);
  window.localStorage.setItem(CANDIDATE_REFRESH_TOKEN_KEY, refreshToken);
}

export function clearCandidateTokens(): void {
  window.localStorage.removeItem(CANDIDATE_TOKEN_KEY);
  window.localStorage.removeItem(CANDIDATE_REFRESH_TOKEN_KEY);
}
