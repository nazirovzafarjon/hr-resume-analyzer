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
import HiringPipeline from "../../components/dashboard/HiringPipeline";
import LineTrendChart from "../../components/charts/LineTrendChart";
import { useChartPalette } from "../../components/charts/chartTheme";
import { APPLICATION_STATUS_LABELS, translateOr } from "../../utils/statusLabels";
import type { ApplicationStatus } from "../../types/candidate";

const STATUS_ORDER: ApplicationStatus[] = ["new", "reviewing", "shortlisted", "interview", "hired", "rejected", "withdrawn"];
const TERMINAL: ApplicationStatus[] = ["rejected", "withdrawn"];

/** /analytics — hiring funnel, score distribution and weekly volume. */
export default function AnalyticsPage() {
  const { t, language } = useLanguage();
  const palette = useChartPalette();
  const [reloadKey, setReloadKey] = useState(0);
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
  }, [t, reloadKey]);

  if (loading && !data) {
    return (
      <div className="page">
        <PageHeader
          title={t("analytics.title") || "Analytics"}
          description={t("analytics.description") || "Pipeline performance at a glance."}
        />
        <SkeletonCards count={4} />
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
              <Button onClick={() => setReloadKey((key) => key + 1)}>
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
    status,
    label: translateOr(t, `statusMeta.application.${status}`, APPLICATION_STATUS_LABELS[status]),
    count: statusMap.get(status) ?? 0,
    isTerminal: TERMINAL.includes(status),
  }));
  const maxBucket = Math.max(1, ...analytics.score_distribution.map((b) => b.count));
  const analyzedCount = analytics.analysis_status_counts.completed;
  const locale = language === "kiril" ? "uz-Cyrl-UZ" : language === "uz" ? "uz-Latn-UZ" : language === "ru" ? "ru-RU" : "en-US";
  const formatWeek = (iso: string) =>
    new Intl.DateTimeFormat(locale, { month: "short", day: "numeric", timeZone: "UTC" }).format(
      new Date(`${iso}T00:00:00Z`),
    );

  const header = (
    <>
      <PageMeta title={t("nav.analytics")} noindex />
      <PageHeader
        title={t("analytics.title") || "Analytics"}
        description={t("analytics.description") || "Pipeline performance at a glance."}
      />
    </>
  );

  if (analytics.total_applications === 0) {
    return (
      <div className="page">
        {header}
        <Card>
          <EmptyState
            title={t("analytics.emptyTitle")}
            message={t("analytics.emptyMessage")}
            action={<Button to={analytics.total_jobs === 0 ? "/jobs/create" : "/jobs"}>{analytics.total_jobs === 0 ? t("jobs.createJob") : t("analytics.emptyAction")}</Button>}
          />
        </Card>
      </div>
    );
  }

  return (
    <div className="page">
      {header}

      <div className="stat-grid">
        <StatCard
          label={t("analytics.openJobs") || "Open jobs"}
          value={analytics.total_jobs}
          hint={t("stats.jobsHint") || "active vacancies"}
        />
        <StatCard
          label={t("stats.applications") || "Applications"}
          value={analytics.total_applications}
          hint={t("stats.applicationsHint") || "received total"}
        />
        <StatCard
          label={t("analytics.avgScore") || "Avg AI score"}
          value={analyzedCount > 0 ? `${Math.round(analytics.avg_ai_score)}%` : "—"}
          hint={t("analytics.avgScoreHint", { count: analyzedCount })}
          tone="primary"
        />
        <StatCard
          label={t("analytics.candidates")}
          value={analytics.total_candidates}
          hint={t("analytics.candidatesHint")}
        />
      </div>

      <div className="dashboard-grid dashboard-grid--even">
        <Card
          title={t("analytics.hiringFunnel") || "Hiring funnel"}
          subtitle={t("analytics.hiringFunnelSubtitle")}
        >
          <HiringPipeline
            stages={funnelStages}
            emptyTitle={t("dashboard.statusChart.emptyTitle")}
            emptyMessage={t("dashboard.statusChart.emptyMessage")}
          />
        </Card>

        <Card
          title={t("analytics.scoreDistribution") || "AI score distribution"}
          subtitle={t("analytics.scoreDistributionSubtitle")}
        >
          {analyzedCount === 0 ? (
            <EmptyState title={t("analytics.noScoresTitle")} message={t("analytics.noScoresMessage")} />
          ) : (
            <ul className="pipeline-list">
              {analytics.score_distribution.map((bucket) => (
                <li key={bucket.bucket} className="pipeline-stage pipeline-stage--compact">
                  <span className="pipeline-label">{bucket.bucket}</span>
                  <span className="pipeline-track" aria-hidden="true">
                    <span className="pipeline-bar" style={{ width: `${(bucket.count / maxBucket) * 100}%` }} />
                  </span>
                  <span className="pipeline-count">{bucket.count}</span>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>

      <LineTrendChart
        title={t("analytics.weeklyVolume") || "Weekly volume"}
        subtitle={t("analytics.weeklyVolumeSubtitle")}
        data={analytics.trend.map((point) => ({ ...point }))}
        xKey="date"
        series={[
          { key: "applications", label: t("stats.applications") || "Applications", color: palette.primary },
          { key: "interviews", label: t("nav.interviews") || "Interviews", color: palette.info },
        ]}
        formatX={formatWeek}
        emptyTitle={t("dashboard.trend.emptyTitle")}
        emptyMessage={t("dashboard.trend.emptyMessage")}
      />
    </div>
  );
}
