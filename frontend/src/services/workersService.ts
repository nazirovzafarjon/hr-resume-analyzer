/**
 * Applications & Candidates (worker) API integration.
 *
 * A Worker *is* an Application in the backend. Once HR moves an application into
 * the candidate pipeline, `candidate_at` is timestamped and `is_candidate` is true.
 */

import { apiRequest } from "./apiClient";
import type {
  Candidate,
  CandidateDetail,
  CandidateStatusUpdate,
} from "../types/worker";

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

/** Fetch workers (applications/candidates) with optional filtering. */
export async function fetchWorkers(params?: WorkerFilterParams): Promise<Candidate[]> {
  return apiRequest<Candidate[]>(`/workers${buildQuery(params)}`, { auth: true });
}

/** Fetch candidates (workers with candidate_at set). */
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

/** Fetch full detail for a single worker (includes form answers, AI analysis, interviews). */
export async function getWorker(id: number): Promise<CandidateDetail> {
  return apiRequest<CandidateDetail>(`/workers/${id}`, { auth: true });
}

/** Update HR-owned statuses on a worker. */
export async function updateWorker(
  id: number,
  patch: CandidateStatusUpdate,
): Promise<CandidateDetail> {
  return apiRequest<CandidateDetail>(`/workers/${id}`, {
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
  return apiRequest<CandidateDetail>(`/workers/${id}/analyze?force=${force}`, {
    method: "POST",
    auth: true,
  });
}

/** Move an application into the candidate pipeline. */
export async function convertToCandidate(id: number): Promise<CandidateDetail> {
  return apiRequest<CandidateDetail>(`/workers/${id}/convert-to-candidate`, {
    method: "POST",
    auth: true,
  });
}

/** Delete a worker/candidate. */
export async function deleteWorker(id: number): Promise<void> {
  return apiRequest<void>(`/workers/${id}`, {
    method: "DELETE",
    auth: true,
  });
}

// Auto-analyze batch APIs

export type AutoAnalyzeAvailableResponse = {
  count: number;
};

export type AutoAnalyzeStartRequest = {
  count: number;
  order: "oldest" | "newest";
  job_id?: number;
};

export type AutoAnalyzeStartResponse = {
  batch_id: number;
  requested_count: number;
  selected_count: number;
  status: string;
};

export type AutoAnalyzeProgressResponse = {
  batch_id: number;
  status: string;
  total: number;
  processed: number;
  successful: number;
  failed: number;
  remaining: number;
  current_application_id: number | null;
  created_at: string | null;
  finished_at: string | null;
};

/** Get the count of NEW applications available for auto-analysis. */
export async function getAutoAnalyzeAvailable(
  job_id?: number,
): Promise<AutoAnalyzeAvailableResponse> {
  const params = job_id ? `?job_id=${job_id}` : "";
  return apiRequest<AutoAnalyzeAvailableResponse>(
    `/workers/auto-analyze/available${params}`,
    { auth: true },
  );
}

/** Start a new auto-analyze batch. */
export async function startAutoAnalyze(
  request: AutoAnalyzeStartRequest,
): Promise<AutoAnalyzeStartResponse> {
  return apiRequest<AutoAnalyzeStartResponse>("/workers/auto-analyze", {
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
    `/workers/auto-analyze/${batchId}`,
    { auth: true },
  );
}

/** Cancel a running or queued auto-analyze batch. */
export async function cancelAutoAnalyze(
  batchId: number,
): Promise<AutoAnalyzeProgressResponse> {
  return apiRequest<AutoAnalyzeProgressResponse>(
    `/workers/auto-analyze/${batchId}/cancel`,
    { method: "POST", auth: true },
  );
}
