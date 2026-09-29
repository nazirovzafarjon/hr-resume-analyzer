import Badge from "./Badge";
import { useLanguage } from "../../contexts/LanguageContext";
import {
  INTERVIEW_FILTER_LABELS,
  INTERVIEW_FILTER_TONES,
  translateOr,
} from "../../utils/statusLabels";
import type { InterviewStatusFilter } from "../../types/application";

/** Status chip for HR-managed interviews (upcoming / completed / cancelled). */
export default function InterviewStatusBadge({
  value,
}: {
  value: InterviewStatusFilter | string;
}) {
  const { t } = useLanguage();
  const key = value as keyof typeof INTERVIEW_FILTER_TONES;
  const tone = INTERVIEW_FILTER_TONES[key] ?? "neutral";
  const label = INTERVIEW_FILTER_LABELS[key] ?? String(value);

  return (
    <Badge tone={tone} dot>
      {translateOr(t, `statusMeta.interviewFilter.${value}`, label)}
    </Badge>
  );
}
