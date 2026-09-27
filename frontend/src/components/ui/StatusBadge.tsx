import Badge from "./Badge";
import { useLanguage } from "../../contexts/LanguageContext";
import {
  HIRING_STATUS_LABELS,
  HIRING_STATUS_TONES,
  INTERVIEW_STATUS_LABELS,
  INTERVIEW_STATUS_TONES,
  JOB_STATUS_LABELS,
  JOB_STATUS_TONES,
  translateOr,
  type DerivedJobStatus,
} from "../../utils/statusLabels";
import type { HiringStatus, InterviewStatus } from "../../types/worker";

type StatusBadgeProps = {
  kind: "hiring" | "interview" | "job";
  value: HiringStatus | InterviewStatus | DerivedJobStatus;
};

/**
 * Readable chip for hiring decisions, interview progress and job status.
 * The label is always text (never colour alone) and is fully translated.
 */
export default function StatusBadge({ kind, value }: StatusBadgeProps) {
  const { t } = useLanguage();

  if (kind === "hiring") {
    const hiring = value as HiringStatus;
    return (
      <Badge tone={HIRING_STATUS_TONES[hiring] ?? "neutral"} dot>
        {translateOr(t, `statusMeta.hiring.${hiring}`, HIRING_STATUS_LABELS[hiring] ?? hiring)}
      </Badge>
    );
  }

  if (kind === "job") {
    const jobStatus = value as DerivedJobStatus;
    return (
      <Badge tone={JOB_STATUS_TONES[jobStatus] ?? "neutral"} dot>
        {translateOr(t, `jobs.status.${jobStatus}`, JOB_STATUS_LABELS[jobStatus] ?? jobStatus)}
      </Badge>
    );
  }

  const interview = value as InterviewStatus;
  const inProcess = interview === "in_process";
  return (
    <Badge tone={INTERVIEW_STATUS_TONES[interview] ?? "neutral"} dot pulse={inProcess}>
      {translateOr(
        t,
        `statusMeta.interview.${interview}`,
        INTERVIEW_STATUS_LABELS[interview] ?? interview,
      )}
    </Badge>
  );
}
