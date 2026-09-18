/**
 * Mock-only domain types for the sections that do not have a backend yet:
 * Applications, Interviews, Analytics extras and Settings.
 * All mock state — no backend changes.
 */

/** Job application submitted through a generated Google Form (mock). */
export type ApplicationStatus =
  | "new"
  | "screening"
  | "shortlisted"
  | "rejected"
  | "hired";

export type Application = {
  id: number;
  job_id: number;
  candidate_id: number;
  candidate_name: string;
  candidate_email: string;
  status: ApplicationStatus;
  ai_score: number;
  ai_summary: string;
  matched_skills: string[];
  missing_skills: string[];
  submitted_at: string;
  resume_file_name: string;
};

/** Scheduled / completed interview (manual HR entry; meeting link pasted by hand). */
export type InterviewStatusFilter = "upcoming" | "completed" | "cancelled";

export type Interview = {
  id: number;
  job_id: number;
  candidate_id: number;
  hr_id: number;
  candidate_name: string;
  job_title: string;
  company_name: string;
  scheduled_at: string;
  duration_minutes: number;
  interviewer: string;
  meeting_link: string | null;
  status: InterviewStatusFilter;
  notes: string | null;
  created_at: string;
  updated_at: string;
};

/** Funnel + time-series data for the Analytics page (mock). */
export type HiringFunnelStage = {
  stage: string;
  count: number;
};

export type ScoreBucket = {
  bucket: string;
  count: number;
};

export type WeeklyVolume = {
  week: string;
  applications: number;
  interviews: number;
};
