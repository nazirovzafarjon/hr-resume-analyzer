import type { HiringStatus } from "./worker";

/** Dashboard types mirror the backend `app/schemas/dashboard.py`. */

export type CategoryBreakdown = {
  category: string;
  jobs: number;
  candidates: number;
};

export type AnalyticsOverview = {
  total_jobs: number;
  total_candidates: number;
  total_leads: number;
  group_by: string;
  breakdown: CategoryBreakdown[];
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

/** A single dashboard KPI card. */
export type Kpi = {
  label: string;
  value: number;
  hint: string;
  trend: string;
};
