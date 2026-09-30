/**
 * Cross-app configuration (see .env.example).
 *
 * The CRM and the public landing site are separate Vite apps, so each needs to
 * know where the other one runs.
 */

function trimTrailingSlash(value: string): string {
  return value.replace(/\/+$/, "");
}

/** Origin of the public landing site; "Back to home" in the sidebar goes here. */
export const LANDING_URL = trimTrailingSlash(
  import.meta.env.VITE_LANDING_URL?.trim() || "http://localhost:5174",
);

/**
 * Cookie domain for the signed-in hint the landing site reads (see
 * auth/tokenStorage). Empty means host-only, which already covers both dev
 * servers (cookies ignore the port). In production set it to the parent
 * domain, e.g. ".example.com", when the apps live on sibling subdomains.
 */
export const SESSION_COOKIE_DOMAIN = import.meta.env.VITE_SESSION_COOKIE_DOMAIN?.trim() ?? "";
