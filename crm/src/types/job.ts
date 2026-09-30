/**
 * Job (vacancy) types. Field names mirror the backend `app/schemas/job.py` so
 * the future API integration needs no renaming.
 */

import type {
  ApplicationFieldDef,
  ApplicationFormConfig,
  ApplicationFormPayload,
} from "./applicationForm";

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
  /** Published application form (owner view) — null when none exists yet. */
  application_form?: ApplicationFormConfig | null;
};

/**
 * Payload used when creating a job. `application_form` carries the reviewed
 * candidate questions; the backend then validates and stores them atomically
 * with the job and returns the public token. Mirrors the backend's
 * `JobCreate`/`JobUpdate` schemas exactly — the AI analysis step
 * (`POST /jobs/analyze`) is a separate, unstored request, so its result is
 * only ever a starting draft for these fields, never persisted itself.
 */
export type JobCreateInput = {
  company_name: string;
  position: string;
  description: string;
  required_skills: string;
  required_experience: string;
  application_form?: ApplicationFormPayload | null;
};

/** Counts of candidates per hiring decision for a job's candidate summary. */
export type JobAnalytics = {
  total: number;
  strong_hires: number;
  hires: number;
  weak_hires: number;
  do_not_hires: number;
};

