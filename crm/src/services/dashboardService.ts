/**
 * Dashboard API service.
 *
 * Provides access to dashboard analytics, recent jobs, and recent leads.
 * All requests are authenticated and scoped to the current user.
 */

import { apiRequest } from "./apiClient";
import type { AnalyticsGroupBy, HiringStatus } from "../types/worker";

export type AnalyticsRange = "7d" | "30d" | "90d";

/**
 * Fetch dashboard overview with optional category grouping.
 * Returns total_jobs, total_candidates, total_leads, and breakdown by category.
 */
export async function fetchDashboardOverview(category: AnalyticsGroupBy = "company") {
  const params = new URLSearchParams({ category });
  return apiRequest<DashboardOverview>(
    `/dashboard/overview?${params}`,
    { auth: true }
  );
}

/**
 * Fetch recent jobs for the current user.
 */
export async function fetchRecentJobs(limit = 5) {
  const params = new URLSearchParams({ limit: String(limit) });
  return apiRequest<RecentJob[]>(
    `/dashboard/recent-jobs?${params}`,
    { auth: true }
  );
}

/**
 * Fetch recent leads/candidates for the current user.
 */
export async function fetchRecentLeads(limit = 5) {
  const params = new URLSearchParams({ limit: String(limit) });
  return apiRequest<RecentLead[]>(
    `/dashboard/recent-leads?${params}`,
    { auth: true }
  );
}

/**
 * Fetch comprehensive analytics data (trend, status distribution, AI
 * processing counts, top jobs, ...) for the given time range.
 */
export async function fetchAnalyticsData(range: AnalyticsRange = "30d") {
  const params = new URLSearchParams({ range });
  return apiRequest<AnalyticsData>(`/dashboard/analytics?${params}`, { auth: true });
}

// ---- Types (mirror app/schemas/dashboard.py) ----

export type DashboardOverview = {
  total_jobs: number;
  total_candidates: number;
  total_leads: number;
  group_by: string;
  breakdown: Array<{
    category: string;
    jobs: number;
    candidates: number;
  }>;
};

export type RecentJob = {
  id: number;
  company_name: string;
  position: string;
  leads_count: number;
  created_at: string;
};

export type RecentLead = {
  id: number;
  name: string;
  email: string;
  company_name: string;
  position: string;
  hiring_status: HiringStatus;
  created_at: string;
};

export type TrendPoint = {
  date: string;
  applications: number;
  interviews: number;
};

export type PreviousPeriod = {
  applications: number;
  interviews: number;
};

export type StatusCount = {
  status: import("../types/worker").ApplicationStatus;
  count: number;
};

export type AnalysisStatusCounts = {
  new: number;
  pending: number;
  analyzing: number;
  completed: number;
  failed: number;
};

export type ScoreDistributionBucket = { bucket: string; count: number };

export type HiringStatusCounts = {
  strong_hire: number;
  hire: number;
  weak_hire: number;
  do_not_hire: number;
};

export type InterviewStatusCounts = {
  in_process: number;
  completed: number;
  not_completed: number;
};

export type TopJob = {
  job_id: number;
  position: string;
  company_name: string;
  applications_count: number;
};

export type AnalyticsData = {
  range: AnalyticsRange;
  trend: TrendPoint[];
  previous_period: PreviousPeriod;
  status_distribution: StatusCount[];
  analysis_status_counts: AnalysisStatusCounts;
  score_distribution: ScoreDistributionBucket[];
  hiring_status_counts: HiringStatusCounts;
  interview_status_counts: InterviewStatusCounts;
  avg_ai_score: number;
  total_jobs: number;
  total_applications: number;
  total_candidates: number;
  top_jobs: TopJob[];
};
