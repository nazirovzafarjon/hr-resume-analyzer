/**
 * Job (vacancy) types. Field names mirror the backend `app/schemas/job.py` so
 * the future API integration needs no renaming.
 */

import type {
  ApplicationFieldDef,
  ApplicationFormConfig,
  ApplicationFormPayload,
} from "./applicationForm";

/** How the vacancy requirements were provided. */
export type JobRequirementSource = "manual" | "file" | "both";

/** Structured AI analysis of a vacancy (from backend AI endpoint). */
export type JobAIAnalysisResult = {
  company_name: string;
  position: string;
  description: string;
  required_skills: string;
  required_experience: string;
  /**
   * AI *suggestions* for the application form, already normalised by the
   * backend against its fixed field-type registry. They are data only —
   * the public form layout never depends on them.
   */
  application_fields?: ApplicationFieldDef[] | null;
};

/** Legacy mock AI analysis (kept for backwards compatibility with existing UI). */
export type JobAIAnalysis = {
  summary: string;
  responsibilities: string[];
  required_skills: string[];
  nice_to_have_skills: string[];
  experience_level: string;
  seniority_score: number;
  clarity_score: number;
  completeness_score: number;
  suggestions: string[];
};

export type JobInput = {
  id: number;
  public_id: string;
  company_name: string;
  position: string;
  description: string;
  required_skills: string;
  required_experience: string;
  leads_count: number;
  created_at: string;
  /** Mock-only extensions — optional so existing jobs keep working. */
  requirement_source?: JobRequirementSource;
  requirement_file_name?: string;
  ai_instructions?: string;
  ai_analysis?: JobAIAnalysis;
  /** Published application form (owner view) — null when none exists yet. */
  application_form?: ApplicationFormConfig | null;
  form_url?: string;
};

/**
 * Payload used when creating a job. `application_form` carries the reviewed
 * candidate questions; the backend then validates and stores them atomically
 * with the job and returns the public token.
 */
export type JobCreateInput = {
  company_name: string;
  position: string;
  description: string;
  required_skills: string;
  required_experience: string;
  requirement_source?: JobRequirementSource;
  requirement_file_name?: string;
  ai_instructions?: string;
  ai_analysis?: JobAIAnalysis;
  application_form?: ApplicationFormPayload | null;
  form_url?: string;
};

/** Counts of candidates per hiring decision for a job's candidate summary. */
export type JobAnalytics = {
  total: number;
  strong_hires: number;
  hires: number;
  weak_hires: number;
  do_not_hires: number;
};

