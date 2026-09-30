import { ArrowRight } from "lucide-react";
import { useI18n } from "../../i18n";
import { appLinks } from "../../lib/config";
import { useSignedIn } from "../../hooks/useSignedIn";

export default function FinalCta() {
  const { t } = useI18n();
  const signedIn = useSignedIn();
  return (
    <section className="final-cta" aria-labelledby="cta-title">
      <div className="container">
        <div className="final-cta-panel" data-reveal>
          <h2 id="cta-title">{t.cta.title}</h2>
          <p>{t.cta.subtitle}</p>
          <div className="hero-actions">
            <a className="btn btn--lg" href={appLinks.register}>
              {t.cta.primary}
              <ArrowRight size={18} aria-hidden="true" />
            </a>
            <a className="btn btn--secondary btn--lg" href={signedIn ? appLinks.workspace : appLinks.login}>
              {signedIn ? t.nav.openWorkspace : t.cta.secondary}
            </a>
            <a className="btn btn--secondary btn--lg" href={appLinks.candidateLogin}>
              {t.cta.candidate}
            </a>
          </div>
        </div>
      </div>
    </section>
  );
}
