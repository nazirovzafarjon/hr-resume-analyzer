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
  return apiRequest<PublicApplication>(`/public/applications/${token}`);
}

/** Submit a candidate application through the public form (no auth). */
export async function submitPublicApplication(
  token: string,
  fields: ApplicationFieldDef[],
  values: ApplicationValues,
  files: Record<string, File | null>
): Promise<void> {
  const formData = buildSubmissionFormData(fields, values, files);
  const response = await fetch(
    `${import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api"}/public/applications/${token}/submit`,
    {
      method: "POST",
      body: formData,
    }
  );
  if (!response.ok) {
    let detail = "Something went wrong. Please try again.";
    try {
      const data = await response.json();
      if (data.detail) detail = data.detail;
    } catch {
      // Ignore JSON parse errors.
    }
    const error = new Error(detail) as Error & { status: number };
    error.status = response.status;
    throw error;
  }
}