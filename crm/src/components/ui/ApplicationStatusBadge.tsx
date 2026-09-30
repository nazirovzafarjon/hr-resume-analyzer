import Badge from "./Badge";
import { useLanguage } from "../../contexts/LanguageContext";
import {
  ANALYSIS_STATUS_LABELS,
  ANALYSIS_STATUS_TONES,
  APPLICATION_STATUS_LABELS,
  APPLICATION_STATUS_TONES,
  translateOr,
} from "../../utils/statusLabels";
import type { AnalysisStatus } from "../../types/candidate";

/**
 * Status chip for job applications and their AI analysis progress.
 * Internal values (e.g. `analyzing`) are never shown — only their labels.
 */
export function ApplicationStatusBadge({
  value,
}: {
  value: ApplicationStatusLike;
}) {
  const { t } = useLanguage();
  const tone = APPLICATION_STATUS_TONES[value as keyof typeof APPLICATION_STATUS_TONES] ?? "neutral";
  const label =
    APPLICATION_STATUS_LABELS[value as keyof typeof APPLICATION_STATUS_LABELS] ??
    String(value);
  const translated = translateOr(t, `statusMeta.application.${value}`, label);

  return (
    <Badge tone={tone} dot>
      {translated}
    </Badge>
  );
}

type ApplicationStatusLike = string;

/** AI analysis state chip; "analyzing" pulses to show work is happening. */
export function AnalysisStatusBadge({ value }: { value: AnalysisStatus | string }) {
  const { t } = useLanguage();
  const key = value as keyof typeof ANALYSIS_STATUS_TONES;
  const tone = ANALYSIS_STATUS_TONES[key] ?? "neutral";
  const analyzing = value === "analyzing";
  const label = ANALYSIS_STATUS_LABELS[key] ?? String(value);
  const translated = translateOr(t, `statusMeta.analysis.${value}`, label);

  return (
    <Badge tone={tone} dot pulse={analyzing}>
      {translated}
    </Badge>
  );
}

/** Default export keeps the historical import style (`import Badge from …`). */
export default ApplicationStatusBadge;
