/**
 * Candidate Portal API types (mirror backend app/schemas/candidate.py).
 *
 * These are candidate-safe shapes: they intentionally have no HR hiring
 * recommendation, interviewer notes or internal AI text.
 */

export type CandidateProfile = {
  id: number;
  email: string;
  full_name: string;
  phone: string | null;
  profile_image: string | null;
  created_at: string;
  /** False for Google-only accounts, which have no local password. */
  has_password: boolean;
  /** False until the candidate confirms the registered email. */
  is_email_verified: boolean;
};

export type CandidateTokens = {
  access_token: string;
  refresh_token: string;
  token_type: string;
};

export type CandidateAuthResult = CandidateTokens & { candidate: CandidateProfile };

export type CandidateStatus =
  | "submitted"
  | "ai_review"
  | "hr_review"
  | "interview_invited"
  | "interview_scheduled"
  | "decision_pending"
  | "accepted"
  | "rejected"
  | "withdrawn";

export type CandidateAnalysisState = "not_analyzed" | "analyzing" | "analyzed" | "failed";
export type CandidateInterviewState = "not_scheduled" | "scheduled" | "completed";

export type CandidateApplicationSummary = {
  id: number;
  position: string;
  company_name: string;
  submitted_at: string;
  status: CandidateStatus;
  analysis_state: CandidateAnalysisState;
  interview_state: CandidateInterviewState;
  next_interview_at: string | null;
};

export type CandidateInterview = {
  id: number;
  application_id: number;
  position: string;
  company_name: string;
  scheduled_at: string;
  duration_minutes: number;
  status: "upcoming" | "completed" | "cancelled";
  is_online: boolean;
  meeting_link: string | null;
};

export type CandidateAIFeedback = {
  state: CandidateAnalysisState;
  match_percentage: number | null;
  matched_skills: string[];
  skills_to_improve: string[];
  requirements_met: string[];
  requirements_to_strengthen: string[];
  analyzed_at: string | null;
};

export type TimelineStepKey = "submitted" | "resume_review" | "hr_review" | "interview" | "decision";
export type TimelineStepState = "done" | "current" | "upcoming" | "skipped" | "unavailable";

export type TimelineStep = {
  key: TimelineStepKey;
  state: TimelineStepState;
  date: string | null;
  outcome: "accepted" | "rejected" | "withdrawn" | null;
};

export type CandidateAnswer = {
  label: string;
  type: string;
  value: string | string[] | null;
  file_attached: boolean;
};

export type CandidateApplicationDetail = CandidateApplicationSummary & {
  job: {
    position: string;
    company_name: string;
    description: string | null;
    required_skills: string | null;
    required_experience: string | null;
  };
  has_resume: boolean;
  answers: CandidateAnswer[];
  analysis: CandidateAIFeedback;
  timeline: TimelineStep[];
  interviews: CandidateInterview[];
};

export type CandidateDashboard = {
  total_applications: number;
  active_applications: number;
  upcoming_interviews: number;
  completed_applications: number;
  next_interview: CandidateInterview | null;
  recent_applications: CandidateApplicationSummary[];
};
