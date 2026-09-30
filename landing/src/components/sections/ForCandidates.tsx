import { ArrowRight, CalendarDays, FileCheck2, Route, Sparkles } from "lucide-react";
import CandidateTimelineCard from "../visuals/CandidateTimelineCard";
import { useI18n } from "../../i18n";
import { appLinks } from "../../lib/config";

const ICONS = [FileCheck2, Route, Sparkles, CalendarDays];

/** The candidate side of the platform: apply, track, understand, prepare. */
export default function ForCandidates() {
  const { t } = useI18n();
  return (
    <section id="for-candidates" className="section" aria-labelledby="candidates-title">
      <div className="container split split--reverse">
        <div className="split-copy" data-reveal>
          <p className="eyebrow">{t.candidates.eyebrow}</p>
          <h2 id="candidates-title" className="section-title">{t.candidates.title}</h2>
          <p className="section-subtitle">{t.candidates.subtitle}</p>
          <ul className="point-list">
            {t.candidates.points.map((point, index) => {
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
          <div className="hero-actions hero-actions--start">
            <a className="btn btn--lg" href={appLinks.candidateRegister}>
              {t.candidates.primary}
              <ArrowRight size={18} aria-hidden="true" />
            </a>
            <a className="btn btn--secondary btn--lg" href={appLinks.candidateLogin}>
              {t.candidates.secondary}
            </a>
          </div>
        </div>
        <div className="split-visual" data-reveal>
          <CandidateTimelineCard />
          <p className="visual-caption">{t.common.sampleData}</p>
        </div>
      </div>
    </section>
  );
}
