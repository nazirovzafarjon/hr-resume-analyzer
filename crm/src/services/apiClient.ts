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
 * Outcome of a refresh attempt.
 *
 * - `ok`: a usable access token (fresh, or one another tab already obtained),
 * - `rejected`: the server refused the refresh token — the session is over,
 * - `unavailable`: network/CORS failure or a 5xx — the session may well still
 *   be valid, so it must NOT be dropped (the request just fails this time).
 */
type RefreshOutcome =
  | { status: "ok"; accessToken: string }
  | { status: "rejected" }
  | { status: "unavailable" };

/**
 * In-flight refresh, shared by every caller in this tab.
 *
 * When a page fires several protected requests with an expired access token,
 * they all 401 at once; without this they would each trigger a refresh, and
 * because refresh tokens are single-use the losers would burn a token they can
 * no longer use and get logged out.
 */
const refreshInFlight: Record<SessionKind, Promise<RefreshOutcome> | null> = {
  hr: null,
  candidate: null,
};

/**
 * Exchange the stored refresh token for a new pair.
 *
 * Implemented with plain fetch on purpose: calling `refreshTokens()` in
 * authService would route back through this module (authService imports it),
 * and a self-referential call here would recurse if the refresh itself 401s.
 *
 * `rejectedAccessToken` is the token the server just refused. If storage
 * already holds a different one, another tab (or an earlier refresh here) has
 * rotated the pair in the meantime, and that token is used instead of
 * spending the — by now already consumed — refresh token.
 */
async function performRefresh(kind: SessionKind, rejectedAccessToken: string | null): Promise<RefreshOutcome> {
  const store = SESSIONS[kind];
  const current = store.getToken();
  if (current && current !== rejectedAccessToken) {
    return { status: "ok", accessToken: current };
  }
  const refreshToken = store.getRefreshToken();
  if (!refreshToken) return { status: "rejected" };

  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${store.refreshPath}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });
  } catch {
    // Network/CORS failure: leave the session alone and let the caller retry.
    return { status: "unavailable" };
  }
  if (response.status >= 500 || response.status === 429) return { status: "unavailable" };
  if (!response.ok) {
    // Another tab may have rotated the pair while this request was in flight;
    // its new token is then the answer, not a sign-out.
    const latest = store.getToken();
    if (latest && latest !== rejectedAccessToken) return { status: "ok", accessToken: latest };
    return { status: "rejected" };
  }
  try {
    const tokens = (await response.json()) as Partial<AuthResponse>;
    if (typeof tokens?.access_token !== "string") return { status: "unavailable" };
    store.save(tokens.access_token, tokens.refresh_token ?? null);
    return { status: "ok", accessToken: tokens.access_token };
  } catch {
    return { status: "unavailable" };
  }
}

/**
 * Run the refresh under a cross-tab lock where the browser supports it (Web
 * Locks), so two tabs never spend the same single-use refresh token: the
 * second tab waits, then finds the first tab's new token in storage.
 */
function refreshWithLock(kind: SessionKind, rejectedAccessToken: string | null): Promise<RefreshOutcome> {
  const locks = typeof navigator !== "undefined" ? navigator.locks : undefined;
  if (!locks?.request) return performRefresh(kind, rejectedAccessToken);
  return locks.request(`resumeAnalyzer.refresh.${kind}`, () => performRefresh(kind, rejectedAccessToken));
}

function refreshAccessToken(kind: SessionKind, rejectedAccessToken: string | null): Promise<RefreshOutcome> {
  refreshInFlight[kind] ??= refreshWithLock(kind, rejectedAccessToken).finally(() => {
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
    const sentToken = store.getToken();
    response = await send(sentToken);
    // Expired (or otherwise rejected) bearer token: refresh once and replay.
    if (response.status === 401 && withAuth) {
      const outcome = await refreshAccessToken(kind, sentToken);
      if (outcome.status === "ok") {
        response = await send(outcome.accessToken);
      } else if (outcome.status === "unavailable") {
        // Could not reach the refresh endpoint: report a connection problem
        // and keep the session, instead of logging the user out.
        throw new ApiError(0, "Unable to connect to the server.");
      }
    }
  } catch (error) {
    if (error instanceof ApiError) throw error;
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
