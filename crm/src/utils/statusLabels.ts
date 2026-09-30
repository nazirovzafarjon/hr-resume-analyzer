import type { AnalysisStatus, ApplicationStatus, HiringStatus, InterviewStatus } from "../types/candidate";
import type { InterviewStatusFilter } from "../types/application";

/** Tone accepted by <Badge />. */
export type StatusTone = "neutral" | "success" | "warning" | "danger" | "info" | "primary";

/**
 * Status presentation layer.
 *
 * Backend/API values are never renamed — `strong_hire` stays `strong_hire` on
 * the wire. These maps only decide how a value is *displayed*: which colour
 * tone it gets, whether it is an in-progress state, and which translation key
 * carries its human-readable label.
 *
 * Labels are also listed in English here so a missing translation still shows
 * readable text instead of a raw key.
 */

export const APPLICATION_STATUS_TONES: Record<ApplicationStatus, StatusTone> = {
  new: "info",
  reviewing: "warning",
  shortlisted: "primary",
  interview: "success",
  hired: "success",
  rejected: "danger",
  withdrawn: "neutral",
};

export const APPLICATION_STATUS_LABELS: Record<ApplicationStatus, string> = {
  new: "New",
  reviewing: "Reviewing",
  shortlisted: "Shortlisted",
  interview: "Interview",
  hired: "Hired",
  rejected: "Rejected",
  withdrawn: "Withdrawn",
};

export const ANALYSIS_STATUS_TONES: Record<AnalysisStatus, StatusTone> = {
  new: "neutral",
  pending: "neutral",
  analyzing: "warning",
  completed: "success",
  failed: "danger",
};

export const ANALYSIS_STATUS_LABELS: Record<AnalysisStatus, string> = {
  new: "Not analyzed",
  pending: "Queued",
  analyzing: "Analyzing",
  completed: "Analyzed",
  failed: "Analysis failed",
};

export const HIRING_STATUS_TONES: Record<HiringStatus, StatusTone> = {
  strong_hire: "success",
  hire: "info",
  weak_hire: "warning",
  do_not_hire: "danger",
};

export const HIRING_STATUS_LABELS: Record<HiringStatus, string> = {
  strong_hire: "Strong hire",
  hire: "Hire",
  weak_hire: "Weak hire",
  do_not_hire: "Do not hire",
};

export const INTERVIEW_STATUS_TONES: Record<InterviewStatus, StatusTone> = {
  in_process: "info",
  completed: "success",
  not_completed: "neutral",
};

export const INTERVIEW_STATUS_LABELS: Record<InterviewStatus, string> = {
  in_process: "In process",
  completed: "Completed",
  not_completed: "Not completed",
};

export const INTERVIEW_FILTER_TONES: Record<InterviewStatusFilter, StatusTone> = {
  upcoming: "info",
  completed: "success",
  cancelled: "danger",
};

export const INTERVIEW_FILTER_LABELS: Record<InterviewStatusFilter, string> = {
  upcoming: "Upcoming",
  completed: "Completed",
  cancelled: "Cancelled",
};

/**
 * Resolve a translated label, falling back to the English map when the
 * translation module has no entry for the key (t() echoes the key back).
 */
export function translateOr(
  t: (key: string) => string,
  key: string,
  fallback: string,
): string {
  const value = t(key);
  return value === key ? fallback : value;
}

/**
 * Job status, derived (never fabricated) from whether the job has a
 * published application form — the backend has no `status` column, so this
 * is a real, already-tracked fact rather than an invented pipeline stage.
 */
export type DerivedJobStatus = "published" | "draft";

export const JOB_STATUS_TONES: Record<DerivedJobStatus, StatusTone> = {
  published: "success",
  draft: "neutral",
};

export const JOB_STATUS_LABELS: Record<DerivedJobStatus, string> = {
  published: "Published",
  draft: "Draft",
};

export function jobStatusFromToken(publicToken: string | null | undefined): DerivedJobStatus {
  return publicToken ? "published" : "draft";
}

/**
 * Colour for an AI match score, so tables communicate quality consistently.
 * Returns "empty" when there is no score yet.
 */
export function scoreTone(score: number | null | undefined): "high" | "mid" | "low" | "empty" {
  if (score === null || score === undefined || Number.isNaN(score) || score <= 0) return "empty";
  if (score >= 75) return "high";
  if (score >= 50) return "mid";
  return "low";
}