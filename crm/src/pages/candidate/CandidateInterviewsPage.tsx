import EmptyState from "../../components/ui/EmptyState";
import PageMeta from "../../components/seo/PageMeta";
import InterviewItem from "../../components/candidate/InterviewItem";
import { PortalError, PortalLoading } from "../../components/candidate/PortalStates";
import { useLanguage } from "../../contexts/LanguageContext";
import { useApiQuery } from "../../hooks/useApiQuery";
import { fetchCandidateInterviews } from "../../services/candidatePortalService";

/** /candidate/interviews — upcoming interviews first, then past ones. */
export default function CandidateInterviewsPage() {
  const { t } = useLanguage();
  const { data, loading, error, reload } = useApiQuery(fetchCandidateInterviews, "interviews");
  const upcoming = (data ?? []).filter((interview) => interview.status === "upcoming");
  // Most recent first for the history.
  const past = (data ?? []).filter((interview) => interview.status !== "upcoming").reverse();

  return (
    <div>
      <PageMeta title={t("portal.nav.interviews")} noindex />
      <section className="portal-welcome">
        <h1>{t("portal.interviews.title")}</h1>
        <p>{t("portal.interviews.subtitle")}</p>
      </section>

      {error && !data ? (
        <div className="portal-section">
          <PortalError error={error} what={t("portal.interviews.what")} onRetry={reload} />
        </div>
      ) : loading && !data ? (
        <div className="portal-section">
          <PortalLoading />
        </div>
      ) : (
        <>
          <section className="portal-section" aria-labelledby="upcoming-interviews">
            <div className="portal-section-head">
              <h2 id="upcoming-interviews">{t("portal.interviews.upcoming")}</h2>
            </div>
            {upcoming.length === 0 ? (
              <EmptyState title={t("portal.interviews.emptyTitle")} message={t("portal.interviews.emptyMessage")} />
            ) : (
              upcoming.map((interview) => <InterviewItem key={interview.id} interview={interview} />)
            )}
          </section>
          {past.length > 0 && (
            <section className="portal-section" aria-labelledby="past-interviews">
              <div className="portal-section-head">
                <h2 id="past-interviews">{t("portal.interviews.past")}</h2>
              </div>
              {past.map((interview) => (
                <InterviewItem key={interview.id} interview={interview} />
              ))}
            </section>
          )}
        </>
      )}
    </div>
  );
}
