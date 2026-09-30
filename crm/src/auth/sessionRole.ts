import { SESSION_ROLES, type SessionRole } from "../types/auth";

/**
 * Read the workspace ("role" claim) from an access token.
 *
 * This only *reads* the server-signed payload to decide what the UI shows;
 * the signature is not (and cannot be) verified here, and nothing in the
 * browser can change what the backend accepts. Editing the token breaks its
 * signature and the API rejects it. Tokens without the claim are HR
 * sessions, matching the backend's default.
 */
export function roleFromToken(token: string): SessionRole {
  try {
    const payload = token.split(".")[1];
    if (!payload) return SESSION_ROLES.USER;
    const json = atob(payload.replace(/-/g, "+").replace(/_/g, "/"));
    const role = (JSON.parse(json) as { role?: unknown }).role;
    return role === SESSION_ROLES.ADMIN ? SESSION_ROLES.ADMIN : SESSION_ROLES.USER;
  } catch {
    return SESSION_ROLES.USER;
  }
}
