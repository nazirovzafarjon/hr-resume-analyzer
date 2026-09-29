import { useEffect, useState } from "react";
import { fetchAnalyticsData, type AnalyticsData } from "../../services/dashboardService";
import { ApiError } from "../../utils/apiError";
import PageHeader from "../../components/ui/PageHeader";
import PageMeta from "../../components/seo/PageMeta";
import Card from "../../components/ui/Card";
import StatCard from "../../components/ui/StatCard";
import EmptyState from "../../components/ui/EmptyState";
import Button from "../../components/ui/Button";
import { SkeletonCards } from "../../components/ui/Skeleton";
import { useLanguage } from "../../contexts/LanguageContext";
import { APPLICATION_STATUS_LABELS, APPLICATION_STATUS_TONES, translateOr } from "../../utils/statusLabels";
import type { ApplicationStatus } from "../../types/worker";

const STATUS_ORDER: ApplicationStatus[] = ["new", "reviewing", "shortlisted", "interview", "rejected", "withdrawn"];
const STATUS_TONE_COLOR: Record<string, string> = {
  success: "var(--color-success)",
  warning: "var(--color-warning)",
  danger: "var(--color-danger)",
  info: "var(--color-info)",
  primary: "var(--color-primary)",
  neutral: "var(--color-neutral)",
};

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
        const analyticsData = await fetchAnalyticsData("90d");
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
  const statusMap = new Map(analytics.status_distribution.map((row) => [row.status, row.count]));
  const funnelStages = STATUS_ORDER.map((status) => ({
    key: status,
    label: translateOr(t, `statusMeta.application.${status}`, APPLICATION_STATUS_LABELS[status]),
    value: statusMap.get(status) ?? 0,
    color: STATUS_TONE_COLOR[APPLICATION_STATUS_TONES[status]],
  }));
  const maxFunnel = Math.max(1, ...funnelStages.map((s) => s.value));
  const maxBucket = Math.max(1, ...analytics.score_distribution.map((b) => b.count));
  const maxTrend = Math.max(1, ...analytics.trend.map((point) => point.applications));

  return (
    <div className="page">
      <PageMeta title={t("nav.analytics")} noindex />
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
          label={t("stats.applications") || "Applications"}
          value={analytics.total_applications}
          hint={t("stats.applicationsHint") || "received total"}
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
          subtitle={t("analytics.hiringFunnelSubtitle")}
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
          subtitle={t("analytics.scoreDistributionSubtitle")}
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
        subtitle={t("analytics.weeklyVolumeSubtitle")}
      >
        <ul className="bar-list">
          {analytics.trend.map((point) => (
            <li key={point.date} className="bar-item">
              <span className="bar-label">
                {new Date(`${point.date}T00:00:00Z`).toLocaleDateString(undefined, { month: "short", day: "numeric", timeZone: "UTC" })}
              </span>
              <span className="bar-track">
                <span
                  className="bar-fill"
                  style={{
                    width: `${(point.applications / maxTrend) * 100}%`,
                    backgroundColor: "var(--color-primary)",
                  }}
                />
              </span>
              <span className="bar-value">
                {point.applications} {t("stats.applications") || "apps"} · {point.interviews} {t("nav.interviews") || "interviews"}
              </span>
            </li>
          ))}
        </ul>
      </Card>
    </div>
  );
}
