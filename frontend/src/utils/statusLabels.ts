import type { AnalysisStatus, ApplicationStatus, HiringStatus, InterviewStatus } from "../types/worker";
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
  interview: "info",
  rejected: "danger",
  withdrawn: "neutral",
};

export const APPLICATION_STATUS_LABELS: Record<ApplicationStatus, string> = {
  new: "New",
  reviewing: "Reviewing",
  shortlisted: "Shortlisted",
  interview: "Interview",
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
 * Colour for an AI match score, so tables communicate quality consistently.
 * Returns "empty" when there is no score yet.
 */
export function scoreTone(score: number | null | undefined): "high" | "mid" | "low" | "empty" {
  if (score === null || score === undefined || Number.isNaN(score) || score <= 0) return "empty";
  if (score >= 75) return "high";
  if (score >= 50) return "mid";
  return "low";
}