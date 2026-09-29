/**
 * Tokens returned after a successful login, registration, Google sign-in or
 * password reset.
 *
 * `access_token` authorizes API calls. `refresh_token` is longer lived, is only
 * ever presented to `POST /api/auth/refresh`, and is optional because the
 * backend also returns it as `null` for accounts seeded before the refresh flow
 * existed.
 */
export type AuthResponse = {
  access_token: string;
  token_type: string;
  refresh_token?: string | null;
};

export type RegisterInput = {
  email: string;
  full_name: string;
  password: string;
};

export type LoginInput = {
  email: string;
  password: string;
};

export type ForgotPasswordInput = {
  email: string;
};

export type ResetPasswordInput = {
  token: string;
  new_password: string;
};

/** "Skip" on the reset page: present the reset token, keep the password. */
export type SkipResetInput = {
  token: string;
};

/**
 * What a reset link points at, as reported by POST /api/auth/verify-reset-token.
 * Used to word the reset page correctly for Google-only accounts.
 */
export type ResetTokenInfo = {
  email: string;
  full_name: string;
  /** False for accounts that have only ever signed in with Google. */
  has_password: boolean;
  /** True when the account is linked to a Google identity. */
  is_google_account: boolean;
};

/** One-time Google authorization code obtained by the frontend OAuth flow. */
export type GoogleAuthInput = {
  code: string;
  /**
   * The redirect URI the code was issued against. Google requires it to match
   * exactly during the backend token exchange: `postmessage` for the JS popup
   * flow, the configured callback URL for the full-page redirect flow.
   */
  redirect_uri?: string;
};
