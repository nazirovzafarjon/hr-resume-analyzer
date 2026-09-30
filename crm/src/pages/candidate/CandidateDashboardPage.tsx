import { ArrowRight, CalendarDays, CircleCheck, FileText, Hourglass } from "lucide-react";
import Button from "../../components/ui/Button";
import EmptyState from "../../components/ui/EmptyState";
import StatCard from "../../components/ui/StatCard";
import PageMeta from "../../components/seo/PageMeta";
import ApplicationCard from "../../components/candidate/ApplicationCard";
import InterviewItem from "../../components/candidate/InterviewItem";
import { PortalError, PortalLoading } from "../../components/candidate/PortalStates";
import { useLanguage } from "../../contexts/LanguageContext";
import { useCandidateAuth } from "../../context/CandidateAuthContext";
import { useApiQuery } from "../../hooks/useApiQuery";
import { fetchCandidateDashboard } from "../../services/candidatePortalService";

/** /candidate — welcome, counts, the next interview and recent applications. */
export default function CandidateDashboardPage() {
  const { t } = useLanguage();
  const { profile } = useCandidateAuth();
  const { data, loading, error, reload } = useApiQuery(fetchCandidateDashboard, "dashboard");
  const firstName = profile?.full_name.split(/\s+/)[0] ?? "";

  return (
    <div>
      <PageMeta title={t("portal.nav.dashboard")} noindex />
      <section className="portal-welcome">
        <h1>{firstName ? t("portal.dashboard.welcome", { name: firstName }) : t("portal.dashboard.welcomeAnonymous")}</h1>
        <p>{t("portal.dashboard.subtitle")}</p>
      </section>

      {error && !data ? (
        <div className="portal-section">
          <PortalError error={error} what={t("portal.dashboard.what")} onRetry={reload} />
        </div>
      ) : loading && !data ? (
        <div className="portal-section">
          <PortalLoading cards />
        </div>
      ) : data ? (
        <>
          <div className="portal-stats">
            <StatCard label={t("portal.dashboard.total")} value={data.total_applications} icon={<FileText size={14} />} />
            <StatCard label={t("portal.dashboard.active")} value={data.active_applications} tone="info" icon={<Hourglass size={14} />} />
            <StatCard label={t("portal.dashboard.interviews")} value={data.upcoming_interviews} tone="primary" icon={<CalendarDays size={14} />} />
            <StatCard label={t("portal.dashboard.completed")} value={data.completed_applications} tone="success" icon={<CircleCheck size={14} />} />
          </div>

          {data.next_interview && (
            <section className="portal-section" aria-labelledby="next-interview">
              <div className="portal-section-head">
                <h2 id="next-interview">{t("portal.dashboard.nextInterview")}</h2>
              </div>
              <InterviewItem interview={data.next_interview} />
            </section>
          )}

          <section className="portal-section" aria-labelledby="recent-applications">
            <div className="portal-section-head">
              <h2 id="recent-applications">{t("portal.dashboard.recent")}</h2>
              {data.total_applications > data.recent_applications.length && (
                <Button variant="link" to="/candidate/applications" icon={<ArrowRight size={14} />}>
                  {t("portal.dashboard.viewAll")}
                </Button>
              )}
            </div>
            {data.recent_applications.length === 0 ? (
              <EmptyState title={t("portal.applications.emptyTitle")} message={t("portal.applications.emptyMessage")} />
            ) : (
              <div className="portal-grid">
                {data.recent_applications.map((application) => (
                  <ApplicationCard key={application.id} application={application} />
                ))}
              </div>
            )}
          </section>
        </>
      ) : null}
    </div>
  );
}
