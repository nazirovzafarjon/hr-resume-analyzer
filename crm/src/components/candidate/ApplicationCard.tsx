import Button from "../ui/Button";
import { useLanguage } from "../../contexts/LanguageContext";
import type { CandidateApplicationSummary } from "../../types/candidatePortal";
import CandidateStatusBadge from "./CandidateStatusBadge";
import { portalDate, portalDateTime } from "./portalFormat";

/** One application at a glance: what, where, when, and where it stands. */
export default function ApplicationCard({ application }: { application: CandidateApplicationSummary }) {
  const { t } = useLanguage();
  const interview =
    application.interview_state === "scheduled" && application.next_interview_at
      ? portalDateTime(application.next_interview_at)
      : t(`portal.interviewState.${application.interview_state}`);

  return (
    <article className="portal-app-card" aria-labelledby={`application-${application.id}-title`}>
      <div>
        <h3 id={`application-${application.id}-title`}>{application.position}</h3>
        <p className="portal-company">{application.company_name}</p>
      </div>
      <dl className="portal-facts">
        <dt>{t("portal.card.applied")}</dt>
        <dd>{portalDate(application.submitted_at)}</dd>
        <dt>{t("portal.card.status")}</dt>
        <dd>
          <CandidateStatusBadge status={application.status} />
        </dd>
        <dt>{t("portal.card.interview")}</dt>
        <dd>{interview}</dd>
        <dt>{t("portal.card.resumeMatch")}</dt>
        <dd>{t(`portal.analysisState.${application.analysis_state}`)}</dd>
      </dl>
      <Button variant="secondary" size="sm" to={`/candidate/applications/${application.id}`}>
        {t("portal.card.view")}
      </Button>
    </article>
  );
}
