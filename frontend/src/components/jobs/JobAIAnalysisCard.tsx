import Card from "../ui/Card";
import { useLanguage } from "../../contexts/LanguageContext";
import type { JobAIAnalysisResult } from "../../types/job";

type AnalysisCardProps = {
  analysis: JobAIAnalysisResult;
};

/** Renders the structured vacancy analysis returned by POST /jobs/analyze. */
export default function JobAIAnalysisCard({ analysis }: AnalysisCardProps) {
  const { t } = useLanguage();
  return (
    <Card title={t("jobs.aiAnalysisTitle")} subtitle={t("jobs.aiAnalysisSubtitle")}>
      <div className="two-col">
        <div>
          <h4 className="mini-heading">{t("jobs.company")}</h4>
          <p className="muted-note">{analysis.company_name || t("jobs.notSpecified")}</p>
          <h4 className="mini-heading">{t("jobs.position")}</h4>
          <p className="muted-note">{analysis.position || t("jobs.notSpecified")}</p>
          <h4 className="mini-heading">{t("jobs.requiredExperience")}</h4>
          <p className="muted-note">{analysis.required_experience || t("jobs.notSpecified")}</p>
        </div>
        <div>
          <h4 className="mini-heading">{t("jobs.skills")}</h4>
          {(() => {
            const skillChips = analysis.required_skills
              .split(",")
              .map((s) => s.trim())
              .filter((s) => s.length > 0);
            return skillChips.length > 0 ? (
              <div className="chip-row">
                {skillChips.map((skill) => (
                  <span key={skill} className="chip chip--info">
                    {skill}
                  </span>
                ))}
              </div>
            ) : (
              <p className="muted-note">{t("jobs.notSpecified")}</p>
            );
          })()}
        </div>
      </div>
      <div>
        <h4 className="mini-heading">{t("jobs.description")}</h4>
        <p className="analysis-summary">{analysis.description || t("jobs.notSpecified")}</p>
      </div>
    </Card>
  );
}
