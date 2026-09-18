import { useEffect, useState } from "react";
import { fetchAnalyticsData, type AnalyticsData } from "../../services/dashboardService";
import { ApiError } from "../../utils/apiError";
import PageHeader from "../../components/ui/PageHeader";
import Card from "../../components/ui/Card";
import StatCard from "../../components/ui/StatCard";
import EmptyState from "../../components/ui/EmptyState";
import Button from "../../components/ui/Button";
import { SkeletonCards } from "../../components/ui/Skeleton";
import { useLanguage } from "../../contexts/LanguageContext";

/** /analytics — hiring funnel, score distribution and weekly volume. */
export default function AnalyticsPage() {
  const { t } = useLanguage();
  const [data, setData] = useState<AnalyticsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;

    async function loadAnalytics() {
      setLoading(true);
      setError(null);

      try {
        const analyticsData = await fetchAnalyticsData();
        if (mounted) {
          setData(analyticsData);
        }
      } catch (err) {
        if (mounted) {
          if (err instanceof ApiError) {
            setError(err.message);
          } else {
            setError(t("analytics.error") || "Failed to load analytics data. Please try again.");
          }
        }
      } finally {
        if (mounted) {
          setLoading(false);
        }
      }
    }

    loadAnalytics();
    return () => {
      mounted = false;
    };
  }, [t]);

  if (loading && !data) {
    return (
      <div className="page">
        <PageHeader
          title={t("analytics.title") || "Analytics"}
          description={t("analytics.description") || "Pipeline performance at a glance."}
        />
        <SkeletonCards count={5} />
      </div>
    );
  }

  if (error && !data) {
    return (
      <div className="page">
        <PageHeader
          title={t("analytics.title") || "Analytics"}
          description={t("analytics.description") || "Pipeline performance at a glance."}
        />
        <Card>
          <EmptyState
            tone="error"
            title={t("analytics.error") || "Unable to load analytics"}
            message={error}
            action={
              <Button onClick={() => window.location.reload()}>
                {t("common.retry") || "Retry"}
              </Button>
            }
          />
        </Card>
      </div>
    );
  }

  const analytics = data!;
  const maxFunnel = Math.max(1, ...Object.values(analytics.funnel));
  const maxBucket = Math.max(1, ...analytics.score_distribution.map((b) => b.count));
  const maxWeek = Math.max(1, ...analytics.weekly_volume.map((w) => w.applications));

  const funnelStages = [
    { key: "applied", label: t("analytics.applied") || "Applied", value: analytics.funnel.applied, color: "var(--color-primary)" },
    { key: "screening", label: t("analytics.screening") || "Screening", value: analytics.funnel.screening, color: "var(--color-warning)" },
    { key: "interview", label: t("analytics.interview") || "Interview", value: analytics.funnel.interview, color: "var(--color-info)" },
    { key: "shortlisted", label: t("analytics.shortlisted") || "Shortlisted", value: analytics.funnel.shortlisted, color: "var(--color-primary)" },
    { key: "hired", label: t("analytics.hired") || "Hired", value: analytics.funnel.hired, color: "var(--color-success)" },
    { key: "rejected", label: t("analytics.rejected") || "Rejected", value: analytics.funnel.rejected, color: "var(--color-danger)" },
  ];

  return (
    <div className="page">
      <PageHeader
        title={t("analytics.title") || "Analytics"}
        description={t("analytics.description") || "Pipeline performance at a glance."}
      />

      <div className="stat-grid">
        <StatCard
          label={t("analytics.openJobs") || "Open jobs"}
          value={analytics.total_jobs}
          hint={t("stats.jobsHint") || "active vacancies"}
          tone="info"
        />
        <StatCard
          label={t("analytics.candidates") || "Candidates"}
          value={analytics.total_candidates}
          hint={t("stats.candidatesHint") || "in pipeline"}
        />
        <StatCard
          label={t("analytics.avgScore") || "Avg AI score"}
          value={`${Math.round(analytics.avg_ai_score)}%`}
          hint="screening quality"
          tone="success"
        />
        <StatCard
          label={t("analytics.strongHires") || "Strong hires"}
          value={analytics.hiring_status_counts.strong_hire}
          hint="top recommendations"
          tone="success"
        />
        <StatCard
          label={t("analytics.hired") || "Hired"}
          value={analytics.hiring_status_counts.hire}
          hint="hired candidates"
          tone="warning"
        />
      </div>

      <div className="dashboard-grid">
        <Card
          title={t("analytics.hiringFunnel") || "Hiring funnel"}
          subtitle="Conversion through candidate pipeline stages."
        >
          <ul className="bar-list">
            {funnelStages.map((stage) => (
              <li key={stage.key} className="bar-item">
                <span className="bar-label">{stage.label}</span>
                <span className="bar-track">
                  <span
                    className="bar-fill"
                    style={{
                      width: `${(stage.value / maxFunnel) * 100}%`,
                      backgroundColor: stage.color,
                    }}
                  />
                </span>
                <span className="bar-value">{stage.value}</span>
              </li>
            ))}
          </ul>
        </Card>

        <Card
          title={t("analytics.scoreDistribution") || "AI score distribution"}
          subtitle="How candidate resumes scored against job criteria."
        >
          <ul className="bar-list">
            {analytics.score_distribution.map((bucket) => (
              <li key={bucket.bucket} className="bar-item">
                <span className="bar-label">{bucket.bucket}</span>
                <span className="bar-track">
                  <span
                    className="bar-fill"
                    style={{
                      width: `${(bucket.count / maxBucket) * 100}%`,
                      backgroundColor: "var(--color-primary)",
                    }}
                  />
                </span>
                <span className="bar-value">{bucket.count}</span>
              </li>
            ))}
          </ul>
        </Card>
      </div>

      <Card
        title={t("analytics.weeklyVolume") || "Weekly volume"}
        subtitle="Applications received per week."
      >
        <ul className="bar-list">
          {analytics.weekly_volume.map((week) => (
            <li key={week.week} className="bar-item">
              <span className="bar-label">{week.week}</span>
              <span className="bar-track">
                <span
                  className="bar-fill"
                  style={{
                    width: `${(week.applications / maxWeek) * 100}%`,
                    backgroundColor: "var(--color-primary)",
                  }}
                />
              </span>
              <span className="bar-value">
                {week.applications} {t("stats.applications") || "apps"} · {week.interviews} {t("nav.interviews") || "interviews"}
              </span>
            </li>
          ))}
        </ul>
      </Card>
    </div>
  );
}
