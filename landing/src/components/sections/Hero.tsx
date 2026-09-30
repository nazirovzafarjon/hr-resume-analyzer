import { ArrowRight, CircleCheck } from "lucide-react";
import DashboardMockup from "../visuals/DashboardMockup";
import { useI18n } from "../../i18n";
import { appLinks } from "../../lib/config";

export default function Hero() {
  const { t } = useI18n();
  return (
    <section className="hero" aria-labelledby="hero-title">
      <div className="hero-backdrop" aria-hidden="true" />
      <div className="container">
        <div className="hero-copy">
          <p className="hero-eyebrow">
            <span className="hero-eyebrow-dot" aria-hidden="true" />
            {t.hero.eyebrow}
          </p>
          <h1 id="hero-title" className="hero-title">
            <span>{t.hero.titleLead}</span> <span className="hero-title-tail">{t.hero.titleTail}</span>
          </h1>
          <p className="hero-subtitle">{t.hero.subtitle}</p>
          <div className="hero-actions">
            <a className="btn btn--lg" href={appLinks.register}>
              {t.hero.primaryCta}
              <ArrowRight size={18} aria-hidden="true" />
            </a>
            <a className="btn btn--secondary btn--lg" href="#features">
              {t.hero.secondaryCta}
            </a>
          </div>
          <p className="hero-note">
            <CircleCheck size={16} aria-hidden="true" />
            {t.hero.note}
          </p>
        </div>

        <div className="hero-visual">
          <DashboardMockup />
          <p className="visual-caption">{t.common.sampleData}</p>
        </div>
      </div>
    </section>
  );
}
