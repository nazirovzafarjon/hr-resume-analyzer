import { API_BASE_URL, apiRequest } from "./apiClient";
import type { AuthResponse } from "../types/auth";
import type {
  ChangePasswordInput,
  ProfileUpdateInput,
  UserProfile,
} from "../types/user";

// The API base URL points at /api; stored image URLs are relative to the
// backend origin (e.g. "/uploads/profile/<id>.jpg"), so strip the suffix.
const BACKEND_ORIGIN = API_BASE_URL.replace(/\/api\/?$/, "");

/**
 * Turn the server-relative `profile_image` path into an absolute URL the
 * browser can load. Absolute URLs (and null) pass through unchanged.
 */
export function profileImageUrl(imagePath: string | null): string | null {
  if (!imagePath) return null;
  if (imagePath.startsWith("http")) return imagePath;
  return `${BACKEND_ORIGIN}${imagePath}`;
}

/** GET /api/auth/me — the authenticated user's own profile. */
export function getCurrentUser(): Promise<UserProfile> {
  return apiRequest<UserProfile>("/auth/me", { auth: true });
}

/**
 * PATCH /api/auth/me — update the signed-in user's name and/or email.
 * Both fields are optional; only the submitted ones reach the backend.
 */
export function updateProfile(input: ProfileUpdateInput): Promise<UserProfile> {
  return apiRequest<UserProfile>("/auth/me", {
    method: "PATCH",
    body: input,
    auth: true,
  });
}

/**
 * PATCH /api/auth/me/password — change the password.
 *
 * The backend verifies the current password, revokes every session issued
 * before the change and answers with a fresh access/refresh pair, which the
 * caller must store (see `AuthContext.signIn`) to stay signed in.
 */
export function changePassword(
  input: ChangePasswordInput,
): Promise<AuthResponse> {
  return apiRequest<AuthResponse>("/auth/me/password", {
    method: "PATCH",
    body: input,
    auth: true,
  });
}

/**
 * POST /api/auth/me/profile-image — upload/replace the profile image.
 *
 * Sent as multipart/form-data; the backend validates the file content and
 * answers with the updated profile.
 */
export function uploadProfileImage(file: File): Promise<UserProfile> {
  const formData = new FormData();
  formData.append("file", file);
  return apiRequest<UserProfile>("/auth/me/profile-image", {
    method: "POST",
    body: formData,
    auth: true,
    formData: true,
  });
}

/** DELETE /api/auth/me/profile-image — remove the profile image (if any). */
export function removeProfileImage(): Promise<UserProfile> {
  return apiRequest<UserProfile>("/auth/me/profile-image", {
    method: "DELETE",
    auth: true,
  });
}