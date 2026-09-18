/**
 * Google OAuth configuration from Vite environment variables (see .env.example).
 *
 * - VITE_GOOGLE_CLIENT_ID: OAuth client id from the Google Cloud Console.
 * - VITE_GOOGLE_REDIRECT_URI: where Google sends the browser back after the
 *   consent screen (defaults to /oauth/callback on the current origin). Must
 *   match the backend GOOGLE_REDIRECT_URI and be registered as an "Authorized
 *   redirect URI" for the client.
 *
 * This module never throws when the variables are missing: an empty client id
 * simply disables the "Continue with Google" UI (see GoogleAuthButton) and
 * stops Google's GSI script from being loaded at all, so email/password auth
 * keeps working without any Google configuration.
 */

/** Safe access to the browser origin (no-op in SSR/test environments). */
function safeOrigin(): string {
  if (typeof window !== "undefined" && window.location?.origin) {
    return window.location.origin;
  }
  return "http://localhost:5173";
}

const RAW_CLIENT_ID: string = import.meta.env.VITE_GOOGLE_CLIENT_ID ?? "";
const REDIRECT_URI: string =
  import.meta.env.VITE_GOOGLE_REDIRECT_URI ?? `${safeOrigin()}/oauth/callback`;

/** Trimmed Google OAuth client id (empty string when not configured). */
export const GOOGLE_CLIENT_ID: string = RAW_CLIENT_ID;

/** Full callback URL Google redirects to after the consent screen. */
export const GOOGLE_REDIRECT_URI: string = REDIRECT_URI;

/**
 * Redirect URI used by Google's JS popup flow. Google's `initCodeClient`
 * always binds popup-issued authorization codes to the special value
 * "postmessage" (the `redirect_uri` option is ignored for popup UX), so the
 * backend must exchange those codes with exactly this value. The button sends
 * it along with the code; the backend allowlist accepts it plus
 * GOOGLE_REDIRECT_URI.
 */
export const POPUP_FLOW_REDIRECT_URI = "postmessage";

/**
 * OAuth scopes requested on the consent screen. Required so the backend can
 * resolve the account after the code exchange:
 * - `openid`  — issues an identity (id_token) for the Google account.
 * - `email`   — returns the verified email address (the account key).
 * - `profile` — returns the display name and avatar picture URL.
 *
 * Must match what the Google Cloud Console OAuth client allows; the backend
 * rejects profiles without `openid`/`email` data (see GoogleAuthService).
 */
export const GOOGLE_AUTH_SCOPES = "openid email profile";

/**
 * True when Sign in with Google may run. When false, the OAuth provider is not
 * mounted and Google's script is not injected - auth falls back to email and
 * password only.
 */
export const GOOGLE_AUTH_ENABLED: boolean = GOOGLE_CLIENT_ID.trim().length > 0;

if (!GOOGLE_AUTH_ENABLED && import.meta.env && import.meta.env.DEV) {
  console.warn(
    "[google-auth] VITE_GOOGLE_CLIENT_ID is not set. " +
      "'Continue with Google' is hidden and the Google scripts are not loaded. " +
      "Set VITE_GOOGLE_CLIENT_ID in a frontend .env file to enable it.",
  );
}
