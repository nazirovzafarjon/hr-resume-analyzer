import { apiRequest } from "./apiClient";
import { fetchAllPages } from "./pagination";
import type { Interview, InterviewStatusFilter } from "../types/application";

/** Counts of interviews per status, powering the metric cards. */
export type InterviewStats = {
  total: number;
  upcoming: number;
  completed: number;
  cancelled: number;
};

/** Payload for scheduling a new interview (candidate selected from the applications list). */
export type InterviewCreateInput = {
  candidate_id: number;
  interviewer: string;
  scheduled_at: string;
  duration_minutes: number;
  meeting_link?: string | null;
  notes?: string | null;
};

/** Partial update payload (PATCH). */
export type InterviewUpdateInput = Partial<InterviewCreateInput> & {
  status?: InterviewStatusFilter;
};

type ListParams = {
  status?: InterviewStatusFilter;
  search?: string;
};

/** Largest page the backend serves for `/interviews` (its `limit` maximum). */
const INTERVIEWS_PAGE_SIZE = 500;

/**
 * Fetch all of the current user's interviews matching the optional
 * status/search filters (read page by page, so nothing past the backend's
 * per-request cap is dropped).
 */
export async function fetchInterviews(params: ListParams = {}): Promise<Interview[]> {
  return fetchAllPages((skip, limit) => {
    const query = new URLSearchParams();
    if (params.status) query.set("status", params.status);
    if (params.search) query.set("search", params.search);
    query.set("skip", String(skip));
    query.set("limit", String(limit));
    return apiRequest<Interview[]>(`/interviews?${query.toString()}`, { auth: true });
  }, INTERVIEWS_PAGE_SIZE);
}

/** Fetch interview counts by status for the metric cards. */
export async function fetchInterviewStats(): Promise<InterviewStats> {
  return apiRequest<InterviewStats>("/interviews/stats", { auth: true });
}

/** Fetch a single interview by id. */
export async function fetchInterview(id: number): Promise<Interview> {
  return apiRequest<Interview>(`/interviews/${id}`, { auth: true });
}

/** Schedule a new interview. */
export async function createInterview(payload: InterviewCreateInput): Promise<Interview> {
  return apiRequest<Interview>("/interviews", { method: "POST", body: payload, auth: true });
}

/** Update an interview (status, notes, meeting link, time, interviewer). */
export async function updateInterview(
  id: number,
  payload: InterviewUpdateInput,
): Promise<Interview> {
  return apiRequest<Interview>(`/interviews/${id}`, { method: "PATCH", body: payload, auth: true });
}

/** Delete an interview. */
export async function deleteInterview(id: number): Promise<void> {
  return apiRequest<void>(`/interviews/${id}`, { method: "DELETE", auth: true });
}

/** Convert a datetime-local input value ("YYYY-MM-DDTHH:MM") to a UTC ISO string. */
export function toUtcIso(localValue: string): string {
  return new Date(localValue).toISOString();
}

/** Convert a UTC ISO string to the local datetime-local input format. */
export function toLocalInputValue(iso: string): string {
  const date = new Date(iso);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(
    date.getHours(),
  )}:${pad(date.getMinutes())}`;
}