/**
 * Environment-driven configuration (see .env.example).
 *
 * Authentication lives in the CRM app, so the landing only needs to know where
 * that app runs. The one backend call it makes is the public Contact form.
 */

function trimTrailingSlash(value: string): string {
  return value.replace(/\/+$/, "");
}

/** Origin of the CRM app (crm/). */
export const APP_URL = trimTrailingSlash(
  import.meta.env.VITE_APP_URL?.trim() || "http://localhost:5173",
);

/** Base URL of the FastAPI backend (same value as the CRM's VITE_API_BASE_URL). */
export const API_BASE_URL = trimTrailingSlash(
  import.meta.env.VITE_API_BASE_URL?.trim() || "http://localhost:8000/api",
);

/** Public address of this site; empty in development. */
export const SITE_URL = trimTrailingSlash(import.meta.env.VITE_SITE_URL?.trim() ?? "");

/** Real contact address, or null when none is configured. */
export const CONTACT_EMAIL: string | null =
  import.meta.env.VITE_CONTACT_EMAIL?.trim() || null;

/**
 * Non-secret cookie the CRM sets while a user is signed in (see
 * crm/src/auth/tokenStorage.ts). It only picks which buttons to show; the CRM
 * still validates the real session when the visitor gets there.
 */
export const SESSION_HINT_COOKIE = "resumeAnalyzer.signedIn";

/**
 * Entry points into the CRM app: the HR workspace (login, register,
 * dashboard) and the Candidate Portal (its own sign-in and account).
 */
export const appLinks = {
  login: `${APP_URL}/login`,
  register: `${APP_URL}/register`,
  workspace: `${APP_URL}/dashboard`,
  candidateLogin: `${APP_URL}/candidate/login`,
  candidateRegister: `${APP_URL}/candidate/register`,
} as const;
