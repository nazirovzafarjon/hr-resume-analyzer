/**
 * Response shapes of the superuser-only /api/admin endpoints
 * (mirrors backend/app/schemas/admin.py).
 */
import type {
  AnalysisStatus,
  ApplicantAnswer,
  ApplicationAnalysis,
  ApplicationStatus,
  HiringStatus,
  InterviewStatus,
  CandidateInterviewSummary,
} from "./candidate";

export type Page<T> = {
  items: T[];
  total: number;
  page: number;
  limit: number;
};

export type SortOrder = "asc" | "desc";

export type CountItem = { key: string; count: number };

export type AuditLogEntry = {
  id: number;
  created_at: string;
  actor_user_id: number | null;
  actor_email: string | null;
  action: string;
  resource_type: string;
  resource_id: string | null;
  details: Record<string, unknown> | null;
  ip_address: string | null;
  user_agent: string | null;
  request_id: string | null;
};

export type FilterOptions = {
  owners: { id: number; full_name: string; email: string }[];
  companies: string[];
};

// Dashboard + analytics ------------------------------------------------------

export type SeriesPoint = {
  date: string;
  registrations: number;
  jobs: number;
  applications: number;
  interviews: number;
  ai_completed: number;
  ai_failed: number;
};

export type AdminDashboard = {
  kpis: {
    users_total: number;
    users_active: number;
    users_inactive: number;
    admins: number;
    jobs: number;
    applications: number;
    candidates: number;
    interviews: number;
    ai_analyzed: number;
    ai_failed: number;
    errors_24h: number;
  };
  trend: SeriesPoint[];
  recent_activity: AuditLogEntry[];
};

export type AnalyticsRange = "7d" | "30d" | "90d" | "12m";

export type AdminAnalytics = {
  range: AnalyticsRange;
  bucket: "day" | "week" | "month";
  series: SeriesPoint[];
  totals: Omit<SeriesPoint, "date">;
  users: { total: number; active: number; inactive: number; admins: number };
  application_status: CountItem[];
  analysis_status: CountItem[];
  hiring_status: CountItem[];
  interview_status: CountItem[];
  score_distribution: CountItem[];
  top_companies: { company: string; jobs: number; applications: number }[];
  top_jobs: {
    job_id: number;
    position: string;
    company_name: string;
    owner_email: string;
    applications: number;
  }[];
  avg_applications_per_job: number;
  avg_ai_score: number | null;
};

// Users ------------------------------------------------------------------------

export type AdminUserRow = {
  id: number;
  email: string;
  full_name: string;
  is_active: boolean;
  is_superuser: boolean;
  has_password: boolean;
  google_linked: boolean;
  created_at: string;
  last_login_at: string | null;
  jobs_count: number;
  applications_count: number;
};

export type AdminUserDetail = AdminUserRow & {
  stats: {
    jobs: number;
    applications: number;
    candidates: number;
    interviews: number;
    ai_analyses: number;
    ai_runs_failed: number;
  };
  ai_provider_source: "default" | "custom";
  recent_jobs: {
    id: number;
    position: string;
    company_name: string;
    applications_count: number;
    created_at: string;
  }[];
  recent_applications: {
    id: number;
    name: string;
    position: string;
    company_name: string;
    application_status: ApplicationStatus;
    analysis_status: AnalysisStatus;
    is_candidate: boolean;
    submitted_at: string;
  }[];
  recent_activity: AuditLogEntry[];
};

/** Payload for the existing PUT /api/users/{id} admin endpoint. */
export type AdminUserUpdate = {
  full_name?: string;
  is_active?: boolean;
  is_superuser?: boolean;
};

// Jobs -------------------------------------------------------------------------

export type AdminJobRow = {
  id: number;
  position: string;
  company_name: string;
  owner_id: number;
  owner_email: string;
  owner_name: string;
  applications_count: number;
  candidates_count: number;
  analyzed_count: number;
  created_at: string;
};

export type AdminJobDetail = AdminJobRow & {
  description: string;
  required_skills: string;
  required_experience: string;
  has_public_form: boolean;
  status_breakdown: CountItem[];
};

// Applications / candidates ----------------------------------------------------

export type AdminWorkerRow = {
  id: number;
  name: string;
  email: string;
  job_id: number;
  position: string;
  company_name: string;
  owner_id: number;
  owner_email: string;
  owner_name: string;
  application_status: ApplicationStatus;
  analysis_status: AnalysisStatus;
  ai_score: number | null;
  ai_recommendation: string | null;
  hiring_status: HiringStatus;
  interview_status: InterviewStatus;
  is_candidate: boolean;
  candidate_at: string | null;
  submitted_at: string;
};

export type AdminWorkerDetail = AdminWorkerRow & {
  analysis_error: string | null;
  analysis: ApplicationAnalysis | null;
  responses: ApplicantAnswer[];
  interviews: CandidateInterviewSummary[];
  has_resume: boolean;
};

export type WorkerSummary = {
  total: number;
  analysis_status: Record<string, number>;
  application_status: Record<string, number>;
  hiring_status: Record<string, number>;
  interview_status: Record<string, number>;
};

export type AdminWorkerPage = Page<AdminWorkerRow> & { summary: WorkerSummary };

// Interviews -------------------------------------------------------------------

export type InterviewSessionStatus = "upcoming" | "completed" | "cancelled";

export type AdminInterviewRow = {
  id: number;
  candidate_id: number;
  candidate_name: string;
  job_id: number;
  position: string;
  company_name: string;
  hr_id: number;
  hr_email: string;
  hr_name: string;
  interviewer: string;
  scheduled_at: string;
  duration_minutes: number;
  status: InterviewSessionStatus;
  created_at: string;
};

export type AdminInterviewPage = Page<AdminInterviewRow> & {
  summary: {
    total: number;
    upcoming: number;
    completed: number;
    cancelled: number;
    overdue: number;
    candidate_progress: Record<string, number>;
  };
};

// AI monitoring ----------------------------------------------------------------

export type AIRunTotals = {
  total: number;
  completed: number;
  failed: number;
  success_rate: number | null;
  avg_duration_ms: number | null;
};

export type AIOverview = {
  runs_all_time: AIRunTotals;
  runs_24h: AIRunTotals;
  analysis_status: CountItem[];
  avg_score: number | null;
  providers: CountItem[];
  failure_categories: CountItem[];
  recent_batches: {
    id: number;
    owner_email: string | null;
    status: string;
    total: number;
    successful: number;
    failed: number;
    skipped: number;
    created_at: string;
    finished_at: string | null;
  }[];
  platform_provider: {
    provider: string;
    model: string | null;
    api_key_configured: boolean;
    custom_provider_users: number;
  };
};

export type AIRunRow = {
  id: number;
  created_at: string;
  kind: "application" | "vacancy";
  status: "completed" | "failed";
  owner_email: string | null;
  job_id: number | null;
  position: string | null;
  company_name: string | null;
  application_id: number | null;
  provider: string | null;
  model: string | null;
  source: string | null;
  duration_ms: number | null;
  score: number | null;
  error_category: string | null;
  http_status: number | null;
  error_message: string | null;
};

// Audit + errors ---------------------------------------------------------------

export type AuditMeta = { actions: string[]; resource_types: string[] };

export type SystemErrorRow = {
  id: number;
  created_at: string;
  request_id: string | null;
  method: string;
  path: string;
  status_code: number;
  error_type: string;
  message: string;
  user_id: number | null;
  user_email: string | null;
};

export type SystemErrorPage = Page<SystemErrorRow> & {
  summary: { last_24h: number; last_7d: number; by_status_7d: CountItem[] };
};

// Health + settings ------------------------------------------------------------

/** "configured" = settings present but not verified (no external call is made). */
export type HealthStatus = "healthy" | "configured" | "degraded" | "down" | "not_configured";

export type HealthReport = {
  status: "healthy" | "degraded" | "down";
  checked_at: string;
  components: {
    key: string;
    status: HealthStatus;
    latency_ms: number | null;
    detail: string;
    metrics: Record<string, string | number | boolean | null>;
  }[];
};

export type AdminSettings = {
  runtime: {
    registration_enabled: boolean;
    updated_at: string | null;
    updated_by_email: string | null;
  };
  configuration: Record<string, Record<string, unknown>>;
};

// Notifications (Contact Inquiries) -------------------------------------------

export type ContactNotificationRow = {
  id: number;
  name: string;
  first_name: string;
  last_name: string;
  email: string;
  subject: string | null;
  message: string;
  is_read: boolean;
  created_at: string;
};

export type ContactNotificationPage = Page<ContactNotificationRow> & {
  unread_count: number;
};
