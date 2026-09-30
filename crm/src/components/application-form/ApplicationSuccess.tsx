/**
 * Success state shown after a public application submission succeeds.
 * Replaces the form so the candidate cannot (and need not) submit again.
 */
import { useEffect, useRef } from "react";
import { CircleCheck } from "lucide-react";
import { useLanguage } from "../../contexts/LanguageContext";

type ApplicationSuccessProps = {
  position?: string;
  company?: string;
  /** The backend said this candidate's application was already received (409). */
  alreadyReceived?: boolean;
};

export default function ApplicationSuccess({
  position,
  company,
  alreadyReceived = false,
}: ApplicationSuccessProps) {
  const { t } = useLanguage();
  const headingRef = useRef<HTMLHeadingElement>(null);

  // The form this replaces was usually scrolled far down: bring the result
  // into view and move focus to it so screen readers announce it.
  useEffect(() => {
    window.scrollTo({ top: 0 });
    headingRef.current?.focus();
  }, []);

  const thanks = position
    ? company
      ? t("apply.successFor", { position, company })
      : t("apply.successForRole", { position })
    : null;

  return (
    <section className="apply-template apply-template--success" aria-label={t("apply.submittedAriaLabel")}>
      <div className="apply-success">
        <div className="apply-success-icon" aria-hidden="true">
          <CircleCheck size={30} />
        </div>
        <h1 ref={headingRef} className="apply-title" tabIndex={-1}>
          {t("apply.successTitle")}
        </h1>
        {thanks && <p className="apply-success-lead">{thanks}</p>}
        <p>{alreadyReceived ? t("apply.alreadyReceived") : t("apply.receivedMessage")}</p>
      </div>
    </section>
  );
}
