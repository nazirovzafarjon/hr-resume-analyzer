import { Sparkles } from "lucide-react";
import { useLanguage } from "../../contexts/LanguageContext";

/**
 * Shown while the real POST /jobs/analyze request is in flight.
 *
 * Honest indeterminate state — the backend has no per-field progress signal,
 * so this never fakes a percentage or a step checklist.
 */
export default function AIProcessingCard() {
  const { t } = useLanguage();
  return (
    <div className="ai-processing" role="status" aria-label={t("jobs.analyzingVacancy")}>
      <div className="ai-processing-header">
        <span className="ai-processing-icon" aria-hidden="true">
          <Sparkles size={20} />
        </span>
        <div>
          <h3>{t("jobs.analyzingVacancy")}</h3>
          <p>{t("jobs.analyzingHint")}</p>
        </div>
      </div>
    </div>
  );
}
