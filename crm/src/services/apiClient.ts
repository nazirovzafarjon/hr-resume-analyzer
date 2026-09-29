import { ApiError } from "../utils/apiError";
import { clearToken, getRefreshToken, getToken, saveTokens } from "../auth/tokenStorage";
import type { AuthResponse } from "../types/auth";

// Backend base URL from Vite env (VITE_API_BASE_URL, see .env.example), with a
// sensible local default so the app works before an .env file is added.
// Exported so services can also reach non-API backend paths (e.g. /uploads).
export const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api";

type RequestOptions = {
  method?: "GET" | "POST" | "PATCH" | "PUT" | "DELETE";
  body?: unknown;
  /** Attach the stored JWT as a Bearer token (use for protected endpoints). */
  auth?: boolean;
  /** Send `body` as multipart/form-data instead of JSON (used for file uploads). */
  formData?: boolean;
};

/**
 * In-flight refresh, shared by every caller.
 *
 * When a page fires several protected requests with an expired access token,
 * they all 401 at once; without this they would each trigger a refresh, and
 * because refresh tokens are single-use the losers would burn a token they can
 * no longer use and get logged out.
 */
let refreshInFlight: Promise<string | null> | null = null;

/**
 * Exchange the stored refresh token for a new pair.
 *
 * Implemented with plain fetch on purpose: calling `refreshTokens()` in
 * authService would route back through this module (authService imports it),
 * and a self-referential call here would recurse if the refresh itself 401s.
 * Returns the new access token, or null when the session is unrecoverable.
 */
async function performRefresh(): Promise<string | null> {
  const refreshToken = getRefreshToken();
  if (!refreshToken) return null;

  try {
    const response = await fetch(`${API_BASE_URL}/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });
    if (!response.ok) return null;
    const data: unknown = await response.json();
    const tokens = data as Partial<AuthResponse>;
    if (typeof tokens?.access_token !== "string") return null;
    saveTokens(tokens.access_token, tokens.refresh_token ?? null);
    return tokens.access_token;
  } catch {
    // Network/CORS failure: leave the session alone and let the caller retry.
    return null;
  }
}

function refreshAccessToken(): Promise<string | null> {
  refreshInFlight ??= performRefresh().finally(() => {
    refreshInFlight = null;
  });
  return refreshInFlight;
}

/** Broadcast a dead session so AuthContext can redirect to /login. */
function forceSignOut(): void {
  clearToken();
  window.dispatchEvent(new Event("auth:unauthorized"));
}

/**
 * Single place for talking to the backend, so the Authorization header and
 * JSON/error parsing are not repeated across services. Every request includes
 * the base URL, so callers only pass the path (e.g. "/auth/login").
 *
 * Protected requests (`auth: true`) that come back 401 are transparently
 * retried once with a refreshed access token; only when the refresh fails is
 * the session dropped.
 */
export async function apiRequest<T>(
  path: string,
  options: RequestOptions = {},
): Promise<T> {
  const send = (accessToken: string | null) => {
    // Multipart bodies must NOT get a JSON Content-Type: the browser has to
    // set its own (with the form boundary), so only JSON requests set it.
    const isFormData = options.formData && options.body instanceof FormData;
    const headers: Record<string, string> = {};
    if (!isFormData) {
      headers["Content-Type"] = "application/json";
    }
    if (options.auth && accessToken) {
      headers["Authorization"] = `Bearer ${accessToken}`;
    }
    return fetch(`${API_BASE_URL}${path}`, {
      method: options.method ?? "GET",
      headers,
      body:
        options.body === undefined
          ? undefined
          : isFormData
            ? (options.body as FormData)
            : JSON.stringify(options.body),
    });
  };

  let response: Response;
  try {
    response = await send(getToken());
    // Expired (or otherwise rejected) bearer token: refresh once and replay.
    if (response.status === 401 && options.auth && getRefreshToken()) {
      const accessToken = await refreshAccessToken();
      if (accessToken) {
        response = await send(accessToken);
      }
    }
  } catch {
    // fetch throws on network failures and CORS problems.
    throw new ApiError(0, "Unable to connect to the server.");
  }

  if (response.status === 204) {
    return undefined as T; // No Content, e.g. logout.
  }

  let data: unknown = null;
  try {
    data = await response.json();
  } catch {
    // Non-JSON bodies are treated as empty.
  }

  if (!response.ok) {
    if (response.status === 401 && options.auth) {
      // Still 401 after the refresh attempt: the stored token is invalid or the
      // session is gone. Drop it and let the auth context redirect to login.
      forceSignOut();
    }
    throw new ApiError(response.status, extractDetail(data));
  }

  return data as T;
}

/** Pull the backend's `detail` field when present, else a generic message. */
function extractDetail(data: unknown): string {
  if (
    data &&
    typeof data === "object" &&
    typeof (data as { detail?: unknown }).detail === "string"
  ) {
    return (data as { detail: string }).detail;
  }
  return "Something went wrong. Please try again.";
}
