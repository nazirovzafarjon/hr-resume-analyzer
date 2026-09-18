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
