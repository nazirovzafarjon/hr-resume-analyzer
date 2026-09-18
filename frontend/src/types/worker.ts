/**
 * Candidate and Application ("worker") types.
 *
 * A Worker record represents an Application attached to a Job. Once moved
 * forward by HR into the candidate pipeline, `is_candidate` becomes true
 * (`candidate_at` timestamp is set).
 *
 * Values match backend `app/schemas/worker.py` and `app/models/worker.py`.
 */

export type ApplicationStatus =
  | "new"
  | "reviewing"
  | "shortlisted"
  | "interview"
  | "rejected"
  | "withdrawn";

export type AnalysisStatus = "new" | "pending" | "analyzing" | "completed" | "failed";

export type HiringStatus = "strong_hire" | "hire" | "weak_hire" | "do_not_hire";

export type InterviewStatus = "in_process" | "completed" | "not_completed";

export type AnalyticsGroupBy = "company" | "position" | "experience";

export type AIRecommendationType =
  | "strong_hire"
  | "hire"
  | "weak_hire"
  | "do_not_hire";

export type ApplicationAnalysis = {
  match_percentage: number;
  summary: string;
  matched_requirements: string[];
  missing_requirements: string[];
  matched_skills: string[];
  missing_skills: string[];
  strengths: string[];
  weaknesses: string[];
  risks: string[];
  experience_analysis: string;
  education_analysis: string;
  relevant_experience: string[];
  relevant_projects: string[];
  ai_recommendation?: AIRecommendationType | null;
  resume_text_available?: boolean;
  analyzed_at?: string | null;
  model?: string;
};

export type ApplicantAnswer = {
  field_id: string;
  key: string;
  label: string;
  type: string;
  value: unknown;
};

export type WorkerInterviewSummary = {
  id: number;
  interviewer: string;
  scheduled_at: string;
  status: string;
  notes?: string | null;
};

export type Candidate = {
  id: number;
  job_id: number;
  name: string;
  email: string;
  resume_path: string;
  ai_score: number;
  application_status: ApplicationStatus;
  analysis_status: AnalysisStatus;
  analysis_error?: string | null;
  analysis_started_at?: string | null;
  hiring_status: HiringStatus;
  interview_status: InterviewStatus;
  is_candidate: boolean;
  candidate_at?: string | null;
  created_at: string;
  submitted_at: string;
  company_name: string;
  position: string;
};

export type CandidateDetail = Candidate & {
  resume_url?: string | null;
  responses: ApplicantAnswer[];
  analysis?: ApplicationAnalysis | null;
  interviews: WorkerInterviewSummary[];
};

export type CandidateStatusUpdate = {
  name?: string;
  email?: string;
  application_status?: ApplicationStatus;
  hiring_status?: HiringStatus;
  interview_status?: InterviewStatus;
};
