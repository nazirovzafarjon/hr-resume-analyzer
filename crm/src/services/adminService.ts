import { apiRequest } from "./apiClient";
import type {
  AdminAnalytics,
  AdminDashboard,
  AdminInterviewPage,
  AdminJobDetail,
  AdminJobRow,
  AdminSettings,
  AdminUserDetail,
  AdminUserRow,
  AdminUserUpdate,
  AdminWorkerDetail,
  AdminWorkerPage,
  AIOverview,
  AIRunRow,
  AnalyticsRange,
  AuditLogEntry,
  AuditMeta,
  FilterOptions,
  HealthReport,
  Page,
  SystemErrorPage,
} from "../types/admin";

/**
 * Client for the superuser-only admin API. Every call is authenticated; the
 * backend answers 403 for non-admin users, which callers surface as an error.
 */

/** Query parameters: empty values are dropped so "All" filters send nothing. */
export type QueryParams = Record<string, string | number | boolean | null | undefined>;

function withQuery(path: string, params: QueryParams = {}): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === "") continue;
    search.set(key, String(value));
  }
  const query = search.toString();
  return query ? `${path}?${query}` : path;
}

function get<T>(path: string, params?: QueryParams): Promise<T> {
  return apiRequest<T>(withQuery(`/admin${path}`, params), { auth: true });
}

export const fetchAdminDashboard = () => get<AdminDashboard>("/dashboard");

export const fetchAdminAnalytics = (range: AnalyticsRange) =>
  get<AdminAnalytics>("/analytics", { range });

export const fetchFilterOptions = () => get<FilterOptions>("/filters");

export const fetchAdminUsers = (params: QueryParams) => get<Page<AdminUserRow>>("/users", params);

export const fetchAdminUser = (id: number) => get<AdminUserDetail>(`/users/${id}`);

/** Activate / deactivate / promote / demote through the existing admin endpoint. */
export function updateAdminUser(id: number, input: AdminUserUpdate): Promise<AdminUserRow> {
  return apiRequest<AdminUserRow>(`/users/${id}`, { method: "PUT", body: input, auth: true });
}

export function deleteAdminUser(id: number): Promise<void> {
  return apiRequest<void>(`/users/${id}`, { method: "DELETE", auth: true });
}

export const fetchAdminJobs = (params: QueryParams) => get<Page<AdminJobRow>>("/jobs", params);

export const fetchAdminJob = (id: number) => get<AdminJobDetail>(`/jobs/${id}`);

export function deleteAdminJob(id: number): Promise<void> {
  return apiRequest<void>(`/admin/jobs/${id}`, { method: "DELETE", auth: true });
}

export const fetchAdminApplications = (params: QueryParams) =>
  get<AdminWorkerPage>("/applications", params);

export const fetchAdminCandidates = (params: QueryParams) =>
  get<AdminWorkerPage>("/candidates", params);

export const fetchAdminApplication = (id: number) => get<AdminWorkerDetail>(`/applications/${id}`);

export const fetchAdminInterviews = (params: QueryParams) =>
  get<AdminInterviewPage>("/interviews", params);

export const fetchAIOverview = () => get<AIOverview>("/ai-analysis");

export const fetchAIRuns = (params: QueryParams) => get<Page<AIRunRow>>("/ai-analysis/runs", params);

export const fetchAuditLogs = (params: QueryParams) => get<Page<AuditLogEntry>>("/audit-logs", params);

export const fetchAuditMeta = () => get<AuditMeta>("/audit-logs/meta");

export const fetchSystemErrors = (params: QueryParams) => get<SystemErrorPage>("/system-errors", params);

export const fetchAdminSettings = () => get<AdminSettings>("/settings");

export function updateAdminSettings(input: { registration_enabled?: boolean }): Promise<AdminSettings> {
  return apiRequest<AdminSettings>("/admin/settings", { method: "PATCH", body: input, auth: true });
}

export const fetchSystemHealth = () => get<HealthReport>("/system-health");
