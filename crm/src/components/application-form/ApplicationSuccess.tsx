/**
 * Success state shown after a public application submission succeeds.
 * Replaces the form so the candidate cannot (and need not) submit again.
 */
import { useLanguage } from "../../contexts/LanguageContext";

type ApplicationSuccessProps = {
  position?: string;
  company?: string;
};

export default function ApplicationSuccess({ position, company }: ApplicationSuccessProps) {
  const { t } = useLanguage();
  const roleLine = [position, company].filter(Boolean).join(" · ");
  return (
    <section className="apply-template apply-template--success" aria-label={t("apply.submittedAriaLabel")}>
      <div className="apply-success" role="status">
        <div className="apply-success-icon" aria-hidden="true">
          ✓
        </div>
        <h1 className="apply-title">{t("apply.successTitle")}</h1>
        <p className="apply-description">{t("apply.thankYou")}</p>
        {roleLine && <p className="apply-description">{roleLine}</p>}
        <p className="apply-description">{t("apply.receivedMessage")}</p>
      </div>
    </section>
  );
}
