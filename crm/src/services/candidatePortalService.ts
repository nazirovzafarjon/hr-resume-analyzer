/**
 * Candidate Portal API calls (`/api/candidate/*`).
 *
 * Every protected call uses the candidate session of the shared API client
 * (`session: "candidate"`): separate tokens, refresh endpoint and sign-out
 * event from the HR workspace.
 */
import { apiRequest } from "./apiClient";
import type {
  CandidateApplicationDetail,
  CandidateApplicationSummary,
  CandidateAuthResult,
  CandidateDashboard,
  CandidateInterview,
  CandidateProfile,
  CandidateTokens,
} from "../types/candidatePortal";

const candidate = { auth: true, session: "candidate" } as const;

export function registerCandidate(payload: {
  email: string;
  full_name: string;
  password: string;
  phone?: string | null;
}): Promise<CandidateAuthResult> {
  return apiRequest("/candidate/auth/register", { method: "POST", body: payload });
}

export function loginCandidate(payload: { email: string; password: string }): Promise<CandidateAuthResult> {
  return apiRequest("/candidate/auth/login", { method: "POST", body: payload });
}

export function logoutCandidate(refreshToken: string | null): Promise<void> {
  return apiRequest("/candidate/auth/logout", {
    ...candidate,
    method: "POST",
    body: { refresh_token: refreshToken },
  });
}

export function requestCandidatePasswordReset(email: string): Promise<{ message: string }> {
  return apiRequest("/candidate/auth/forgot-password", { method: "POST", body: { email } });
}

export function resetCandidatePassword(token: string, newPassword: string): Promise<CandidateAuthResult> {
  return apiRequest("/candidate/auth/reset-password", {
    method: "POST",
    body: { token, new_password: newPassword },
  });
}

export function fetchCandidateProfile(): Promise<CandidateProfile> {
  return apiRequest("/candidate/profile", candidate);
}

export function updateCandidateProfile(changes: {
  full_name?: string;
  email?: string;
  phone?: string | null;
}): Promise<CandidateProfile> {
  return apiRequest("/candidate/profile", { ...candidate, method: "PATCH", body: changes });
}

export function changeCandidatePassword(currentPassword: string, newPassword: string): Promise<CandidateTokens> {
  return apiRequest("/candidate/profile/password", {
    ...candidate,
    method: "PATCH",
    body: { current_password: currentPassword, new_password: newPassword },
  });
}

export function uploadCandidateProfileImage(file: File): Promise<CandidateProfile> {
  const body = new FormData();
  body.append("file", file);
  return apiRequest("/candidate/profile/image", { ...candidate, method: "POST", body, formData: true });
}

export function removeCandidateProfileImage(): Promise<CandidateProfile> {
  return apiRequest("/candidate/profile/image", { ...candidate, method: "DELETE" });
}

export function fetchCandidateDashboard(): Promise<CandidateDashboard> {
  return apiRequest("/candidate/dashboard", candidate);
}

export function fetchCandidateApplications(): Promise<CandidateApplicationSummary[]> {
  return apiRequest("/candidate/applications", candidate);
}

export function fetchCandidateApplication(id: number): Promise<CandidateApplicationDetail> {
  return apiRequest(`/candidate/applications/${id}`, candidate);
}

export function downloadCandidateResume(id: number): Promise<Blob> {
  return apiRequest(`/candidate/applications/${id}/resume`, { ...candidate, responseType: "blob" });
}

export function fetchCandidateInterviews(): Promise<CandidateInterview[]> {
  return apiRequest("/candidate/interviews", candidate);
}

export function fetchCandidateInterview(id: number): Promise<CandidateInterview> {
  return apiRequest(`/candidate/interviews/${id}`, candidate);
}
