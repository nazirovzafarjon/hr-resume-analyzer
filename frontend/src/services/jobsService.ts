/**
 * Jobs (vacancy) API integration.
 *
 * Provides CRUD operations for jobs, AI-powered vacancy analysis,
 * and the public application-form endpoints.
 */
import { apiRequest } from "./apiClient";
import type { JobInput, JobCreateInput, JobAIAnalysisResult } from "../types/job";
import type { ApplicationFieldDef, ApplicationFormConfig } from "../types/applicationForm";

/** Fetch the current user's jobs. */
export async function fetchJobs(): Promise<JobInput[]> {
  return apiRequest<JobInput[]>("/jobs", { auth: true });
}

/** Fetch a single job by ID. */
export async function fetchJob(id: number): Promise<JobInput> {
  return apiRequest<JobInput>(`/jobs/${id}`, { auth: true });
}

/** Create a new job. */
export async function createJob(input: JobCreateInput): Promise<JobInput> {
  return apiRequest<JobInput>("/jobs", {
    method: "POST",
    body: input,
    auth: true,
  });
}

/** Update an existing job. */
export async function updateJob(id: number, input: Partial<JobCreateInput>): Promise<JobInput> {
  return apiRequest<JobInput>(`/jobs/${id}`, {
    method: "PUT",
    body: input,
    auth: true,
  });
}

/** Delete a job. */
export async function deleteJob(id: number): Promise<void> {
  await apiRequest<void>(`/jobs/${id}`, {
    method: "DELETE",
    auth: true,
  });
}

/** Analyze a vacancy using AI and return structured job information. */
export async function analyzeVacancy(content: string): Promise<JobAIAnalysisResult> {
  return apiRequest<JobAIAnalysisResult>("/jobs/analyze", {
    method: "POST",
    body: { content },
    auth: true,
  });
}

// ---- Application form endpoints ----

/** Get the application-form config for a job (HR view). */
export async function fetchApplicationForm(jobId: number): Promise<ApplicationFormConfig> {
  return apiRequest<ApplicationFormConfig>(`/jobs/${jobId}/application-form`, { auth: true });
}

/** Update the application-form fields for a job. */
export async function updateApplicationForm(
  jobId: number,
  fields: ApplicationFieldDef[]
): Promise<ApplicationFormConfig> {
  return apiRequest<ApplicationFormConfig>(`/jobs/${jobId}/application-form`, {
    method: "PUT",
    body: { fields },
    auth: true,
  });
}

/** Publish (re)generate the application form's public link for a job. */
export async function publishApplicationForm(
  jobId: number,
  regenerateToken = false
): Promise<ApplicationFormConfig> {
  return apiRequest<ApplicationFormConfig>(`/jobs/${jobId}/application-form/publish`, {
    method: "POST",
    body: { regenerate_token: regenerateToken },
    auth: true,
  });
}

/** Delete the application form for a job. */
export async function deleteApplicationForm(jobId: number): Promise<void> {
  await apiRequest<void>(`/jobs/${jobId}/application-form`, {
    method: "DELETE",
    auth: true,
  });
}
