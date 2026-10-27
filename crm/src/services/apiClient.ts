import { ApiError } from "../utils/apiError";
import {
  clearCandidateTokens,
  clearToken,
  getCandidateRefreshToken,
  getCandidateToken,
  getRefreshToken,
  getToken,
  saveCandidateTokens,
  saveTokens,
} from "../auth/tokenStorage";
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
  /** Return the successful response body as a Blob (file downloads). */
  responseType?: "json" | "blob";
  /**
   * Which session's tokens to use: the HR/admin workspace (default) or the
   * Candidate Portal. The two never share tokens, refresh endpoints or
   * sign-out events.
   */
  session?: SessionKind;
  /**
   * Attach the session's token when one is stored, but do not require it
   * (e.g. the public application form, which guests may also submit).
   */
  optionalAuth?: boolean;
};

export type SessionKind = "hr" | "candidate";

type SessionStore = {
  getToken: () => string | null;
  getRefreshToken: () => string | null;
  save: (access: string, refresh: string | null) => void;
  clear: () => void;
  refreshPath: string;
  /** Window event broadcast when the session is dead. */
  unauthorizedEvent: string;
};

const SESSIONS: Record<SessionKind, SessionStore> = {
  hr: {
    getToken,
    getRefreshToken,
    save: (access, refresh) => saveTokens(access, refresh),
    clear: clearToken,
    refreshPath: "/auth/refresh",
    unauthorizedEvent: "auth:unauthorized",
  },
  candidate: {
    getToken: getCandidateToken,
    getRefreshToken: getCandidateRefreshToken,
    save: (access, refresh) => (refresh ? saveCandidateTokens(access, refresh) : clearCandidateTokens()),
    clear: clearCandidateTokens,
    refreshPath: "/candidate/auth/refresh",
    unauthorizedEvent: "candidate:unauthorized",
  },
};

/**
 * In-flight refresh, shared by every caller.
 *
 * When a page fires several protected requests with an expired access token,
 * they all 401 at once; without this they would each trigger a refresh, and
 * because refresh tokens are single-use the losers would burn a token they can
 * no longer use and get logged out.
 */
const refreshInFlight: Record<SessionKind, Promise<string | null> | null> = {
  hr: null,
  candidate: null,
};

/**
 * Exchange the stored refresh token for a new pair.
 *
 * Implemented with plain fetch on purpose: calling `refreshTokens()` in
 * authService would route back through this module (authService imports it),
 * and a self-referential call here would recurse if the refresh itself 401s.
 * Returns the new access token, or null when the session is unrecoverable.
 */
async function performRefresh(kind: SessionKind): Promise<string | null> {
  const store = SESSIONS[kind];
  const refreshToken = store.getRefreshToken();
  if (!refreshToken) return null;

  try {
    const response = await fetch(`${API_BASE_URL}${store.refreshPath}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });
    if (!response.ok) return null;
    const data: unknown = await response.json();
    const tokens = data as Partial<AuthResponse>;
    if (typeof tokens?.access_token !== "string") return null;
    store.save(tokens.access_token, tokens.refresh_token ?? null);
    return tokens.access_token;
  } catch {
    // Network/CORS failure: leave the session alone and let the caller retry.
    return null;
  }
}

function refreshAccessToken(kind: SessionKind): Promise<string | null> {
  refreshInFlight[kind] ??= performRefresh(kind).finally(() => {
    refreshInFlight[kind] = null;
  });
  return refreshInFlight[kind];
}

/** Broadcast a dead session so the matching auth context redirects to its login. */
function forceSignOut(kind: SessionKind): void {
  SESSIONS[kind].clear();
  window.dispatchEvent(new Event(SESSIONS[kind].unauthorizedEvent));
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
  const store = SESSIONS[options.session ?? "hr"];
  const kind = options.session ?? "hr";
  const withAuth = options.auth || (options.optionalAuth && store.getToken() !== null);
  const send = (accessToken: string | null) => {
    // Multipart bodies must NOT get a JSON Content-Type: the browser has to
    // set its own (with the form boundary), so only JSON requests set it.
    const isFormData = options.formData && options.body instanceof FormData;
    const headers: Record<string, string> = {};
    if (!isFormData) {
      headers["Content-Type"] = "application/json";
    }
    if (withAuth && accessToken) {
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
    response = await send(store.getToken());
    // Expired (or otherwise rejected) bearer token: refresh once and replay.
    if (response.status === 401 && withAuth && store.getRefreshToken()) {
      const accessToken = await refreshAccessToken(kind);
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

  if (options.responseType === "blob" && response.ok) {
    return (await response.blob()) as T;
  }

  let data: unknown = null;
  try {
    data = await response.json();
  } catch {
    // Non-JSON bodies are treated as empty.
  }

  if (!response.ok) {
    if (response.status === 401 && withAuth) {
      // Still 401 after the refresh attempt: the stored token is invalid or the
      // session is gone. Drop it and let the auth context redirect to login.
      forceSignOut(kind);
    }
    throw new ApiError(response.status, extractDetail(data), extractCode(data));
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

/** Pull the backend's machine-readable `code` field when present. */
function extractCode(data: unknown): string | undefined {
  if (
    data &&
    typeof data === "object" &&
    typeof (data as { code?: unknown }).code === "string"
  ) {
    return (data as { code: string }).code;
  }
  return undefined;
}
