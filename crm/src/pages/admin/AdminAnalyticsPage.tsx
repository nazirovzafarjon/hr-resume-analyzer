import { useSearchParams } from "react-router-dom";
import PageHeader from "../../components/ui/PageHeader";
import PageMeta from "../../components/seo/PageMeta";
import Button from "../../components/ui/Button";
import EmptyState from "../../components/ui/EmptyState";
import StatCard from "../../components/ui/StatCard";
import { SkeletonCards } from "../../components/ui/Skeleton";
import SegmentedControl from "../../components/dashboard/SegmentedControl";
import LineTrendChart from "../../components/charts/LineTrendChart";
import BarComparisonChart from "../../components/charts/BarComparisonChart";
import { formatScore } from "../../components/admin/badges";
import { useLanguage } from "../../contexts/LanguageContext";
import { useApiQuery } from "../../hooks/useApiQuery";
import { fetchAdminAnalytics } from "../../services/adminService";
import { getErrorMessage } from "../../utils/apiError";
import { translateOr } from "../../utils/statusLabels";
import type { AnalyticsRange, CountItem } from "../../types/admin";
import { formatMonth, formatShortDate } from "./adminFormat";

const RANGES: AnalyticsRange[] = ["7d", "30d", "90d", "12m"];

export default function AdminAnalyticsPage() {
  const { t } = useLanguage();
  const [params, setParams] = useSearchParams();
  const requested = params.get("range") as AnalyticsRange | null;
  const range: AnalyticsRange = requested && RANGES.includes(requested) ? requested : "30d";
  const { data, loading, error, reload } = useApiQuery(() => fetchAdminAnalytics(range), range);
  const firstLoad = loading && !data;
  const formatX = data?.bucket === "month" ? formatMonth : formatShortDate;

  const bars = (items: CountItem[] | undefined, group: string) =>
    (items ?? []).map((item) => ({
      key: item.key,
      label: translateOr(t, `statusMeta.${group}.${item.key}`, item.key),
      value: item.count,
    }));

  const chartState = {
    loading: firstLoad,
    error: error && !data ? getErrorMessage(error, t("errors.loadMessage")) : null,
    onRetry: reload,
    errorTitle: t("errors.loadTitle"),
    retryLabel: t("common.retry"),
    emptyTitle: t("admin.analytics.emptyTitle"),
    emptyMessage: t("admin.analytics.emptyMessage"),
  };

  return (
    <div className="page">
      <PageMeta title={t("admin.nav.analytics")} noindex />
      <PageHeader
        title={t("admin.analytics.title")}
        description={t("admin.analytics.description")}
        action={
          <SegmentedControl
            ariaLabel={t("admin.analytics.range")}
            value={range}
            onChange={(value) => setParams({ range: value }, { replace: true })}
            options={RANGES.map((value) => ({ value, label: t(`admin.analytics.ranges.${value}`) }))}
            disabled={loading}
          />
        }
      />

      {error && !data ? (
        <EmptyState
          tone="error"
          title={t("errors.loadTitle")}
          message={getErrorMessage(error, t("errors.loadMessage"))}
          action={<Button onClick={reload}>{t("common.retry")}</Button>}
        />
      ) : firstLoad || !data ? (
        <SkeletonCards count={4} />
      ) : (
        <div className="stat-grid">
          <StatCard
            label={t("admin.analytics.newUsers")}
            value={data.totals.registrations}
            hint={t("admin.analytics.usersHint", {
              total: data.users.total,
              active: data.users.active,
              inactive: data.users.inactive,
            })}
          />
          <StatCard label={t("admin.analytics.newJobs")} value={data.totals.jobs} />
          <StatCard
            label={t("admin.analytics.newApplications")}
            value={data.totals.applications}
            hint={t("admin.analytics.perJob", { value: data.avg_applications_per_job })}
          />
          <StatCard
            label={t("admin.analytics.aiRuns")}
            value={data.totals.ai_completed + data.totals.ai_failed}
            hint={t("admin.analytics.aiHint", {
              failed: data.totals.ai_failed,
              score: formatScore(data.avg_ai_score),
            })}
            tone={data.totals.ai_failed > 0 ? "warning" : "default"}
          />
        </div>
      )}

      <div className="dashboard-grid dashboard-grid--even">
        <LineTrendChart
          {...chartState}
          title={t("admin.analytics.usersChart")}
          data={data?.series ?? []}
          xKey="date"
          formatX={formatX}
          series={[
            { key: "registrations", label: t("admin.series.registrations") },
            { key: "jobs", label: t("admin.series.jobs") },
          ]}
        />
        <LineTrendChart
          {...chartState}
          title={t("admin.analytics.applicationsChart")}
          data={data?.series ?? []}
          xKey="date"
          formatX={formatX}
          series={[
            { key: "applications", label: t("admin.series.applications") },
            { key: "interviews", label: t("admin.series.interviews") },
          ]}
        />
      </div>

      <LineTrendChart
        {...chartState}
        title={t("admin.analytics.aiChart")}
        subtitle={t("admin.analytics.aiChartHint")}
        data={data?.series ?? []}
        xKey="date"
        formatX={formatX}
        series={[
          { key: "ai_completed", label: t("admin.series.aiCompleted") },
          { key: "ai_failed", label: t("admin.series.aiFailed") },
        ]}
      />

      <div className="dashboard-grid dashboard-grid--even">
        <BarComparisonChart
          {...chartState}
          title={t("admin.analytics.applicationStatus")}
          subtitle={t("admin.analytics.inPeriod")}
          data={bars(data?.application_status, "application")}
          valueLabel={t("admin.series.applications")}
        />
        <BarComparisonChart
          {...chartState}
          title={t("admin.analytics.scoreDistribution")}
          subtitle={t("admin.analytics.scoreHint")}
          data={(data?.score_distribution ?? []).map((item) => ({
            key: item.key,
            label: `${item.key}%`,
            value: item.count,
          }))}
          valueLabel={t("admin.series.applications")}
        />
        <BarComparisonChart
          {...chartState}
          title={t("admin.analytics.hiringStatus")}
          subtitle={t("admin.analytics.hiringHint")}
          data={bars(data?.hiring_status, "hiring")}
          valueLabel={t("admin.series.applications")}
        />
        <BarComparisonChart
          {...chartState}
          title={t("admin.analytics.interviewStatus")}
          subtitle={t("admin.analytics.inPeriod")}
          data={bars(data?.interview_status, "interview")}
          valueLabel={t("admin.series.applications")}
        />
        <BarComparisonChart
          {...chartState}
          title={t("admin.analytics.topCompanies")}
          subtitle={t("admin.analytics.topCompaniesHint")}
          data={(data?.top_companies ?? []).map((row) => ({
            key: row.company,
            label: row.company,
            value: row.jobs,
          }))}
          valueLabel={t("admin.series.jobs")}
        />
        <BarComparisonChart
          {...chartState}
          title={t("admin.analytics.topJobs")}
          subtitle={t("admin.analytics.inPeriod")}
          data={(data?.top_jobs ?? []).map((row) => ({
            key: String(row.job_id),
            label: `${row.position} · ${row.company_name}`,
            value: row.applications,
          }))}
          valueLabel={t("admin.series.applications")}
        />
      </div>
    </div>
  );
}
