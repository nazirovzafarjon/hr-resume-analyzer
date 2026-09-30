/**
 * Public API service for candidate applications (no authentication required).
 *
 * NEW flow: applications are answered via a public link of the form
 *   /apply/{public_token}
 * The token is the credential — no JWT is required.
 */
import { apiRequest } from "./apiClient";
import type {
  ApplicationFieldDef,
  ApplicationValues,
  PublicApplication,
} from "../types/applicationForm";
import { buildSubmissionFormData } from "../utils/applicationFields";

/** Fetch the public application page payload (no auth). */
export async function getPublicApplication(
  token: string
): Promise<PublicApplication> {
  return apiRequest<PublicApplication>(`/public/applications/${encodeURIComponent(token)}`);
}

/**
 * Submit a candidate application through the public form (no auth).
 *
 * Multipart body (`values` JSON + one part per file field) sent through the
 * shared client, so failures surface as `ApiError` with the backend's
 * candidate-safe `detail` and its status (422 validation, 409 duplicate,
 * 404 link gone, 0 network).
 */
export function submitPublicApplication(
  token: string,
  fields: ApplicationFieldDef[],
  values: ApplicationValues,
  files: Record<string, File | null>
): Promise<void> {
  return apiRequest<void>(`/public/applications/${encodeURIComponent(token)}/submit`, {
    method: "POST",
    body: buildSubmissionFormData(fields, values, files),
    formData: true,
  });
}
