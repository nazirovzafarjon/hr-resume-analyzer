import type { CSSProperties } from "react";
import { Check, Circle, Sparkles } from "lucide-react";
import { useI18n } from "../../i18n";

const SCORE = 87;
const MATCHED = ["Python", "FastAPI", "PostgreSQL", "REST API"];
const MISSING = ["Docker"];

/** Static example of a resume-analysis result (never calls the AI service). */
export default function AnalysisCard() {
  const { t } = useI18n();
  const c = t.analysis.card;

  return (
    <div className="analysis-card">
      <div className="analysis-card-head">
        <span className="analysis-card-label">
          <Sparkles size={14} aria-hidden="true" />
          {c.label}
        </span>
        <span className="sample-tag">{t.common.sampleData}</span>
      </div>

      <div className="analysis-card-candidate">
        <span className="avatar avatar--lg" aria-hidden="true">{c.name.charAt(0)}</span>
        <div>
          <p className="analysis-card-caption">{c.candidate}</p>
          <p className="analysis-card-name">{c.name}</p>
          <p className="analysis-card-role">{c.role}</p>
        </div>
        <div
          className="score-ring"
          style={{ "--score": `${SCORE * 3.6}deg` } as CSSProperties}
          role="img"
          aria-label={`${c.match}: ${SCORE}%`}
        >
          <span aria-hidden="true">
            <strong>{SCORE}%</strong>
            <small>{c.match}</small>
          </span>
        </div>
      </div>

      <div className="analysis-card-skills">
        <div>
          <p className="analysis-card-caption">{c.matched}</p>
          <ul className="skill-list">
            {MATCHED.map((skill) => (
              <li key={skill} className="skill skill--matched">
                <Check size={13} aria-hidden="true" />
                {skill}
              </li>
            ))}
          </ul>
        </div>
        <div>
          <p className="analysis-card-caption">{c.missing}</p>
          <ul className="skill-list">
            {MISSING.map((skill) => (
              <li key={skill} className="skill skill--missing">
                <Circle size={11} aria-hidden="true" />
                {skill}
              </li>
            ))}
          </ul>
        </div>
      </div>

      <div className="analysis-card-summary">
        <p className="analysis-card-caption">{c.summaryLabel}</p>
        <p>{c.summary}</p>
      </div>

      <div className="analysis-card-footer">
        <span className="analysis-card-caption">{c.recommendationLabel}</span>
        <span className="pill pill--success">{c.recommendation}</span>
      </div>
    </div>
  );
}
