/**
 * Applications & Candidates API integration (`/api/applications`).
 *
 * Every record is an application. Once HR moves one into the candidate
 * pipeline, `candidate_at` is timestamped and `is_candidate` is true.
 */

import { apiRequest } from "./apiClient";
import type {
  Candidate,
  CandidateDetail,
  CandidateStatusUpdate,
} from "../types/candidate";

export type WorkerFilterParams = {
  job_id?: number;
  application_status?: string;
  hiring_status?: string;
  interview_status?: string;
  candidate_only?: boolean;
  search?: string;
  sort?: string;
  skip?: number;
  limit?: number;
};

function buildQuery(params?: WorkerFilterParams): string {
  if (!params) return "";
  const query = new URLSearchParams();
  if (params.job_id !== undefined) query.set("job_id", String(params.job_id));
  if (params.application_status) query.set("application_status", params.application_status);
  if (params.hiring_status) query.set("hiring_status", params.hiring_status);
  if (params.interview_status) query.set("interview_status", params.interview_status);
  if (params.candidate_only !== undefined) query.set("candidate_only", String(params.candidate_only));
  if (params.search) query.set("search", params.search);
  if (params.sort) query.set("sort", params.sort);
  if (params.skip !== undefined) query.set("skip", String(params.skip));
  if (params.limit !== undefined) query.set("limit", String(params.limit));
  const queryString = query.toString();
  return queryString ? `?${queryString}` : "";
}

/** Fetch applications (and candidates) with optional filtering. */
export async function fetchWorkers(params?: WorkerFilterParams): Promise<Candidate[]> {
  return apiRequest<Candidate[]>(`/applications${buildQuery(params)}`, { auth: true });
}

/** Fetch candidates (applications with candidate_at set). */
export async function fetchCandidates(params?: WorkerFilterParams): Promise<Candidate[]> {
  return fetchWorkers({ ...params, candidate_only: true });
}

/** Fetch all applications for a specific job. */
export async function fetchCandidatesByJob(jobId: number): Promise<Candidate[]> {
  return fetchWorkers({ job_id: jobId });
}

/** Fetch applications across all jobs. */
export async function fetchApplications(params?: WorkerFilterParams): Promise<Candidate[]> {
  return fetchWorkers(params);
}

/** Fetch full detail for a single application (includes form answers, AI analysis, interviews). */
export async function getWorker(id: number): Promise<CandidateDetail> {
  return apiRequest<CandidateDetail>(`/applications/${id}`, { auth: true });
}

/** Update HR-owned statuses on an application. */
export async function updateWorker(
  id: number,
  patch: CandidateStatusUpdate,
): Promise<CandidateDetail> {
  return apiRequest<CandidateDetail>(`/applications/${id}`, {
    method: "PATCH",
    body: patch,
    auth: true,
  });
}

/** Trigger AI analysis on a submitted application. */
export async function analyzeWorker(
  id: number,
  force: boolean = false,
): Promise<CandidateDetail> {
  return apiRequest<CandidateDetail>(`/applications/${id}/analyze?force=${force}`, {
    method: "POST",
    auth: true,
  });
}

/** Move an application into the candidate pipeline. */
export async function convertToCandidate(id: number): Promise<CandidateDetail> {
  return apiRequest<CandidateDetail>(`/applications/${id}/convert-to-candidate`, {
    method: "POST",
    auth: true,
  });
}

/** Delete an application/candidate. */
export async function deleteWorker(id: number): Promise<void> {
  return apiRequest<void>(`/applications/${id}`, {
    method: "DELETE",
    auth: true,
  });
}

/**
 * GET /api/applications/{id}/resume — the stored CV (owner only).
 *
 * Fetched with the bearer token like every protected call, so the file is
 * never reachable through a public URL.
 */
export function fetchResume(id: number, download = false): Promise<Blob> {
  return apiRequest<Blob>(`/applications/${id}/resume${download ? "?download=true" : ""}`, {
    auth: true,
    responseType: "blob",
  });
}

// Auto-analyze batch APIs

/** A company/position pair that has applications waiting for analysis. */
export type AutoAnalyzeFilterOption = {
  company_name: string;
  position: string;
  count: number;
};

export type AutoAnalyzeAvailableResponse = {
  /** Eligible applications matching the requested filters. */
  count: number;
  options: AutoAnalyzeFilterOption[];
};

export type AutoAnalyzeFilters = {
  job_id?: number;
  /** Omitted or "" = all companies / positions. */
  company?: string;
  position?: string;
};

export type AutoAnalyzeStartRequest = AutoAnalyzeFilters & {
  count: number;
  order: "oldest" | "newest";
};

export type AutoAnalyzeStartResponse = {
  batch_id: number;
  requested_count: number;
  selected_count: number;
  available_count: number;
  remaining_count: number;
  status: string;
};

export type AutoAnalyzeProgressResponse = {
  batch_id: number;
  status: string;
  total: number;
  processed: number;
  successful: number;
  failed: number;
  skipped: number;
  remaining: number;
  current_application_id: number | null;
  created_at: string | null;
  finished_at: string | null;
};

/** Count applications Auto Analyze would pick, plus the filter choices. */
export async function getAutoAnalyzeAvailable(
  filters: AutoAnalyzeFilters = {},
): Promise<AutoAnalyzeAvailableResponse> {
  const params = new URLSearchParams();
  if (filters.job_id) params.set("job_id", String(filters.job_id));
  if (filters.company) params.set("company", filters.company);
  if (filters.position) params.set("position", filters.position);
  const query = params.toString();
  return apiRequest<AutoAnalyzeAvailableResponse>(
    `/applications/auto-analyze/available${query ? `?${query}` : ""}`,
    { auth: true },
  );
}

/** Start a new auto-analyze batch. */
export async function startAutoAnalyze(
  request: AutoAnalyzeStartRequest,
): Promise<AutoAnalyzeStartResponse> {
  return apiRequest<AutoAnalyzeStartResponse>("/applications/auto-analyze", {
    method: "POST",
    body: request,
    auth: true,
  });
}

/** Get the progress of an auto-analyze batch. */
export async function getAutoAnalyzeProgress(
  batchId: number,
): Promise<AutoAnalyzeProgressResponse> {
  return apiRequest<AutoAnalyzeProgressResponse>(
    `/applications/auto-analyze/${batchId}`,
    { auth: true },
  );
}

/** Cancel a running or queued auto-analyze batch. */
export async function cancelAutoAnalyze(
  batchId: number,
): Promise<AutoAnalyzeProgressResponse> {
  return apiRequest<AutoAnalyzeProgressResponse>(
    `/applications/auto-analyze/${batchId}/cancel`,
    { method: "POST", auth: true },
  );
}

// ---------------------------------------------------------------------------
// Candidate Comparison API
// ---------------------------------------------------------------------------

export type CandidateComparison = {
  application_id: number;
  job_id: number;
  requirements_fit_score: number;
  relative_percentile: number;
  comparison_pool_size: number;
  rank: number;
  comparison_scope: string;
};

export type ApplicationComparisonResponse = {
  has_comparison: boolean;
  reason?: string | null;
  application_id?: number;
  job_id?: number;
  requirements_fit_score?: number;
  relative_percentile?: number;
  comparison_pool_size?: number;
  rank?: number;
  comparison_scope?: string;
};

export type JobComparisonsResponse = {
  job_id: number;
  total_analyzed: number;
  comparisons: CandidateComparison[];
};

/** Get comparative analysis for one application. */
export async function getApplicationComparison(
  applicationId: number,
): Promise<ApplicationComparisonResponse> {
  return apiRequest<ApplicationComparisonResponse>(
    `/applications/${applicationId}/comparison`,
    { auth: true },
  );
}

/** Get comparative analysis for all candidates in a job. */
export async function getJobComparisons(jobId: number): Promise<JobComparisonsResponse> {
  return apiRequest<JobComparisonsResponse>(
    `/applications/jobs/${jobId}/comparisons`,
    { auth: true },
  );
}
