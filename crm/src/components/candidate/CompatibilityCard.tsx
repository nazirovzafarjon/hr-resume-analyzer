import { CircleCheck, Sparkles, TrendingUp } from "lucide-react";
import Card from "../ui/Card";
import { useLanguage } from "../../contexts/LanguageContext";
import type { CandidateAIFeedback } from "../../types/candidatePortal";

function Chips({ items, kind }: { items: string[]; kind: "match" | "gap" }) {
  return (
    <ul className="portal-chips">
      {items.map((item) => (
        <li key={item} className={`portal-chip portal-chip--${kind}`}>
          {kind === "match" ? <CircleCheck size={12} aria-hidden="true" /> : <TrendingUp size={12} aria-hidden="true" />}
          {item}
        </li>
      ))}
    </ul>
  );
}

/**
 * Resume ↔ job compatibility, candidate-safe.
 *
 * IMPORTANT: candidate-facing AI feedback is sanitized by the backend (only
 * match percentage and skill/requirement lists). All sentences here are
 * neutral UI copy built from those lists — never an HR recommendation,
 * recruiter notes, rankings or raw model text. The hiring decision belongs to
 * the hiring team, and the card says so.
 */
export default function CompatibilityCard({ analysis }: { analysis: CandidateAIFeedback }) {
  const { t } = useLanguage();
  const title = t("portal.ai.title");

  if (analysis.state !== "analyzed" || analysis.match_percentage === null) {
    const state = analysis.state === "analyzed" ? "not_analyzed" : analysis.state;
    return (
      <Card title={title} icon={<Sparkles size={16} />}>
        <p className="portal-timeline-title" style={{ marginTop: 0 }} role="status">
          {t(`portal.ai.${state}.title`)}
        </p>
        <p className="portal-muted" style={{ marginBottom: 0 }}>
          {t(`portal.ai.${state}.message`)}
        </p>
      </Card>
    );
  }

  const strengths = [...analysis.matched_skills, ...analysis.requirements_met];
  const gaps = [...analysis.skills_to_improve, ...analysis.requirements_to_strengthen];
  const value = analysis.match_percentage;

  return (
    <Card title={title} icon={<Sparkles size={16} />}>
      <div className="portal-match">
        <div
          className="portal-match-ring"
          style={{ ["--value" as string]: value }}
          role="img"
          aria-label={t("portal.ai.matchAria", { value })}
        >
          <span>{value}%</span>
        </div>
        <p className="portal-muted" style={{ margin: 0 }}>
          {t(value >= 70 ? "portal.ai.summaryStrong" : value >= 40 ? "portal.ai.summaryPartial" : "portal.ai.summaryLow")}
        </p>
      </div>

      {analysis.matched_skills.length > 0 && (
        <>
          <p className="portal-subheading">{t("portal.ai.strongMatches")}</p>
          <Chips items={analysis.matched_skills} kind="match" />
        </>
      )}
      {analysis.requirements_met.length > 0 && (
        <>
          <p className="portal-subheading">{t("portal.ai.requirementsMet")}</p>
          <Chips items={analysis.requirements_met} kind="match" />
        </>
      )}
      {gaps.length > 0 && (
        <>
          <p className="portal-subheading">{t("portal.ai.toStrengthen")}</p>
          <Chips items={gaps} kind="gap" />
          <p className="portal-muted">
            {t("portal.ai.suggestion", { items: gaps.slice(0, 3).join(", ") })}
          </p>
        </>
      )}
      {strengths.length === 0 && gaps.length === 0 && <p className="portal-muted">{t("portal.ai.noDetails")}</p>}
      <p className="portal-note">{t("portal.ai.disclaimer")}</p>
    </Card>
  );
}
