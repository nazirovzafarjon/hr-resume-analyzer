import { apiRequest } from "./apiClient";
import type {
  AuthResponse,
  ForgotPasswordInput,
  GoogleAuthInput,
  LoginInput,
  RegisterInput,
  ResetPasswordInput,
  ResetTokenInfo,
  SessionRole,
  SignInResult,
  SkipResetInput,
} from "../types/auth";

/** POST /api/auth/register — create an account and receive a token pair. */
export function register(input: RegisterInput): Promise<SignInResult> {
  return apiRequest<SignInResult>("/auth/register", {
    method: "POST",
    body: input,
  });
}

/** POST /api/auth/login — exchange credentials for a token pair. */
export function login(input: LoginInput): Promise<SignInResult> {
  return apiRequest<SignInResult>("/auth/login", {
    method: "POST",
    body: input,
  });
}

/**
 * POST /api/auth/logout — the backend revokes the access token and the
 * refresh token sent here, so the session (and its workspace) cannot resume.
 */
export function logout(refreshToken: string | null): Promise<void> {
  return apiRequest<void>("/auth/logout", {
    method: "POST",
    auth: true,
    body: refreshToken ? { refresh_token: refreshToken } : undefined,
  });
}

/**
 * POST /api/auth/select-role with the selection token from sign-in.
 * Deliberately unauthenticated (`auth: false`): the selection token is its
 * own credential and must never be sent as a bearer token or refreshed.
 */
export function selectRole(selectionToken: string, role: SessionRole): Promise<AuthResponse> {
  return apiRequest<AuthResponse>("/auth/select-role", {
    method: "POST",
    body: { role, selection_token: selectionToken },
  });
}

/** POST /api/auth/select-role with the current session: switch workspace. */
export function switchRole(role: SessionRole): Promise<AuthResponse> {
  return apiRequest<AuthResponse>("/auth/select-role", {
    method: "POST",
    auth: true,
    body: { role },
  });
}

/** POST /api/auth/forgot-password — request a password reset link. */
export function forgotPassword(
  input: ForgotPasswordInput,
): Promise<{ message: string }> {
  return apiRequest<{ message: string }>("/auth/forgot-password", {
    method: "POST",
    body: input,
  });
}

/**
 * POST /api/auth/reset-password — set a new password with a reset token.
 *
 * Returns a fresh access/refresh pair: the backend signs the user in as part of
 * the change, so the caller stores the tokens instead of bouncing to /login.
 */
export function resetPassword(input: ResetPasswordInput): Promise<SignInResult> {
  return apiRequest<SignInResult>("/auth/reset-password", {
    method: "POST",
    body: input,
  });
}

/**
 * POST /api/auth/skip-reset — keep the current password, mint a session.
 *
 * Backs the "Skip" button on the reset page.
 */
export function skipPasswordReset(input: SkipResetInput): Promise<SignInResult> {
  return apiRequest<SignInResult>("/auth/skip-reset", {
    method: "POST",
    body: input,
  });
}

/**
 * POST /api/auth/verify-reset-token — describe the account behind a reset link.
 *
 * Lets the page say "add a password" for Google-only accounts instead of
 * "change your password". Throws ApiError(400) when the link is bad or expired.
 */
export function verifyResetToken(input: SkipResetInput): Promise<ResetTokenInfo> {
  return apiRequest<ResetTokenInfo>("/auth/verify-reset-token", {
    method: "POST",
    body: input,
  });
}

/**
 * POST /api/auth/refresh — exchange the refresh token for a new pair.
 *
 * The explicit counterpart to the endpoint (use it from a "renew session"
 * action). The automatic path lives in `apiClient.performRefresh`, which calls
 * the endpoint with plain fetch instead of routing back through here: this
 * module imports `apiRequest`, so using it for the retry would be circular, and
 * a 401 on the refresh call itself would otherwise recurse.
 *
 * This request deliberately carries no bearer token, so a rejection surfaces as
 * a plain ApiError(401) rather than triggering the client's sign-out broadcast.
 */
export function refreshTokens(refreshToken: string): Promise<AuthResponse> {
  return apiRequest<AuthResponse>("/auth/refresh", {
    method: "POST",
    body: { refresh_token: refreshToken },
  });
}

/** POST /api/auth/google — exchange a Google OAuth authorization code for a token. */
export function loginWithGoogle(
  code: string,
  redirectUri?: string,
): Promise<SignInResult> {
  return apiRequest<SignInResult>("/auth/google", {
    method: "POST",
    body: { code, redirect_uri: redirectUri } satisfies GoogleAuthInput,
  });
}
