/**
 * Dashboard API service.
 *
 * Provides access to dashboard analytics, recent jobs, and recent leads.
 * All requests are authenticated and scoped to the current user.
 */

import { apiRequest } from "./apiClient";

/**
 * Fetch dashboard overview with optional category grouping.
 * Returns total_jobs, total_candidates, total_leads, and breakdown by category.
 */
export async function fetchDashboardOverview(
  category: "company" | "position" | "experience" = "company",
) {
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
 * Fetch comprehensive analytics data for the Analytics page.
 */
export async function fetchAnalyticsData() {
  return apiRequest<AnalyticsData>("/dashboard/analytics", { auth: true });
}

// ---- Types ----

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
  hiring_status: import("../types/worker").HiringStatus;
  created_at: string;
};

export type AnalyticsData = {
  funnel: {
    applied: number;
    screening: number;
    interview: number;
    shortlisted: number;
    hired: number;
    rejected: number;
  };
  score_distribution: Array<{ bucket: string; count: number }>;
  weekly_volume: Array<{ week: string; applications: number; interviews: number }>;
  hiring_status_counts: {
    strong_hire: number;
    hire: number;
    weak_hire: number;
    do_not_hire: number;
  };
  interview_status_counts: {
    in_process: number;
    completed: number;
    not_completed: number;
  };
  avg_ai_score: number;
  total_jobs: number;
  total_candidates: number;
};
