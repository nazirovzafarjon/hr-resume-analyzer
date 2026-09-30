import type { BadgeTone } from "../ui/Badge";
import { API_BASE_URL } from "../../services/apiClient";
import type { CandidateStatus } from "../../types/candidatePortal";

/**
 * Candidate-facing status presentation. Friendly wording only (never HR
 * terms like "shortlisted"); the tone is always paired with the text label,
 * so status is never communicated by colour alone.
 */
export const CANDIDATE_STATUS_TONES: Record<CandidateStatus, BadgeTone> = {
  submitted: "info",
  ai_review: "info",
  hr_review: "warning",
  interview_invited: "primary",
  interview_scheduled: "primary",
  decision_pending: "warning",
  accepted: "success",
  rejected: "neutral",
  withdrawn: "neutral",
};

/** Date in the visitor's locale, e.g. "28 Sep 2026". */
export function portalDate(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
}

/** Time in the visitor's locale, e.g. "14:00". */
export function portalTime(iso: string): string {
  return new Date(iso).toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
}

/** Weekday + date + time, e.g. "Wed, 30 Sep 2026, 14:00". */
export function portalDateTime(iso: string): string {
  return new Date(iso).toLocaleString(undefined, {
    weekday: "short",
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

/** Uploaded images are served by the backend origin (not under /api). */
export function candidateImageUrl(path: string | null): string | null {
  if (!path) return null;
  return `${API_BASE_URL.replace(/\/api\/?$/, "")}${path}`;
}
