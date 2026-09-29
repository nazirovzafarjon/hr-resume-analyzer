import { ListChecks, MessageSquareText, Percent } from "lucide-react";
import AnalysisCard from "../visuals/AnalysisCard";
import { useI18n } from "../../i18n";

const ICONS = [Percent, ListChecks, MessageSquareText];

export default function ResumeAnalysis() {
  const { t } = useI18n();
  return (
    <section id="resume-analysis" className="section section--alt" aria-labelledby="analysis-title">
      <div className="container split">
        <div className="split-copy" data-reveal>
          <p className="eyebrow">{t.analysis.eyebrow}</p>
          <h2 id="analysis-title" className="section-title">{t.analysis.title}</h2>
          <p className="section-subtitle">{t.analysis.subtitle}</p>
          <ul className="point-list">
            {t.analysis.points.map((point, index) => {
              const Icon = ICONS[index];
              return (
                <li key={point.title}>
                  <span className="icon-tile icon-tile--sm" aria-hidden="true">
                    <Icon size={16} />
                  </span>
                  <span>
                    <strong>{point.title}</strong>
                    <span>{point.text}</span>
                  </span>
                </li>
              );
            })}
          </ul>
        </div>
        <div className="split-visual" data-reveal>
          <AnalysisCard />
        </div>
      </div>
    </section>
  );
}
