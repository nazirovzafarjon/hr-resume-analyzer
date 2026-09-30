import Badge from "../ui/Badge";
import { useLanguage } from "../../contexts/LanguageContext";
import type { CandidateStatus } from "../../types/candidatePortal";
import { CANDIDATE_STATUS_TONES } from "./portalFormat";

export default function CandidateStatusBadge({ status }: { status: CandidateStatus }) {
  const { t } = useLanguage();
  return (
    <Badge tone={CANDIDATE_STATUS_TONES[status]} dot pulse={status === "ai_review"}>
      {t(`portal.status.${status}`)}
    </Badge>
  );
}
