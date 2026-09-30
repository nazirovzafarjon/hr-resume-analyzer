import EmptyState from "../../components/ui/EmptyState";
import PageMeta from "../../components/seo/PageMeta";
import ApplicationCard from "../../components/candidate/ApplicationCard";
import { PortalError, PortalLoading } from "../../components/candidate/PortalStates";
import { useLanguage } from "../../contexts/LanguageContext";
import { useApiQuery } from "../../hooks/useApiQuery";
import { fetchCandidateApplications } from "../../services/candidatePortalService";

/** /candidate/applications — every application the candidate submitted. */
export default function CandidateApplicationsPage() {
  const { t } = useLanguage();
  const { data, loading, error, reload } = useApiQuery(fetchCandidateApplications, "applications");

  return (
    <div>
      <PageMeta title={t("portal.nav.applications")} noindex />
      <section className="portal-welcome">
        <h1>{t("portal.applications.title")}</h1>
        <p>{t("portal.applications.subtitle")}</p>
      </section>
      <div className="portal-section">
        {error && !data ? (
          <PortalError error={error} what={t("portal.applications.what")} onRetry={reload} />
        ) : loading && !data ? (
          <PortalLoading cards />
        ) : data && data.length === 0 ? (
          <EmptyState title={t("portal.applications.emptyTitle")} message={t("portal.applications.emptyMessage")} />
        ) : (
          <div className="portal-grid">
            {data?.map((application) => <ApplicationCard key={application.id} application={application} />)}
          </div>
        )}
      </div>
    </div>
  );
}
