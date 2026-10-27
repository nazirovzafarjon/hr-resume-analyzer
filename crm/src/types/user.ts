import type { SessionRole } from "./auth";

/**
 * The signed-in HR user's own profile, as returned by the /api/auth/me
 * endpoints (GET and PATCH).
 */
export type UserProfile = {
  id: number;
  email: string;
  full_name: string;
  /**
   * Server-relative URL of the uploaded profile image
   * (e.g. "/uploads/profile/<id>.jpg"), or null when none is set.
   */
  profile_image: string | null;
  /** False for Google-only accounts, which have no password to change. */
  has_password: boolean;
  /** False until the account confirms its email; the panel is gated until then. */
  is_email_verified: boolean;
  /**
   * Platform administrator. Only used to show/guard the admin panel in the
   * UI; the backend re-checks it on every admin request.
   */
  is_superuser: boolean;
  /** Workspaces this account may use, and the one the current session is in. */
  available_roles: SessionRole[];
  active_role: SessionRole;
};

/** Editable subset of the profile — both fields optional (PATCH /api/auth/me). */
export type ProfileUpdateInput = {
  full_name?: string;
  email?: string;
};

/** Payload for PATCH /api/auth/me/password. */
export type ChangePasswordInput = {
  current_password: string;
  new_password: string;
};

/** AI providers a user can connect (mirrors the backend's supported set). */
export type AIProviderName =
  | "openrouter"
  | "groq"
  | "gemini"
  | "openai"
  | "deepseek"
  | "anthropic"
  | "generic";

/**
 * GET /api/auth/me/ai-provider — which provider the user's analyses use.
 * Never contains the API key, only a masked hint of its last characters.
 * ``base_url`` is shown for ``generic`` provider.
 */
export type AIProviderSettings = {
  configured: boolean;
  source: "custom" | "default";
  provider: AIProviderName | null;
  model_id: string | null;
  masked_api_key: string | null;
  updated_at: string | null;
  /** False when the server cannot encrypt keys (custom providers disabled). */
  can_save: boolean;
  /** True when AI features need the user's own provider (no platform fallback). */
  required: boolean;
  supported_providers: AIProviderName[];
  /** Base URL used for the provider's API (user-supplied for generic). */
  base_url: string | null;
};

export type AIProviderInput = {
  provider: AIProviderName;
  model_id: string;
  /** Omit to keep the saved key (same provider only). */
  api_key?: string;
  /** Required for ``generic`` provider; must be HTTPS and pass SSRF checks. */
  base_url?: string;
};

export type AIProviderTestResult = {
  ok: boolean;
  message: string;
};
