import { Check } from "lucide-react";
import AnalyticsCard from "../visuals/AnalyticsCard";
import { useI18n } from "../../i18n";

export default function AnalyticsPreview() {
  const { t } = useI18n();
  return (
    <section id="analytics" className="section" aria-labelledby="analytics-title">
      <div className="container split split--reverse">
        <div className="split-copy" data-reveal>
          <p className="eyebrow">{t.analytics.eyebrow}</p>
          <h2 id="analytics-title" className="section-title">{t.analytics.title}</h2>
          <p className="section-subtitle">{t.analytics.subtitle}</p>
          <ul className="check-list">
            {t.analytics.points.map((point) => (
              <li key={point}>
                <Check size={16} aria-hidden="true" />
                {point}
              </li>
            ))}
          </ul>
        </div>
        <div className="split-visual" data-reveal>
          <AnalyticsCard />
        </div>
      </div>
    </section>
  );
}
