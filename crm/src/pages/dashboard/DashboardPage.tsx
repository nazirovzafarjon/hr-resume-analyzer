import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  ArrowRight,
  Briefcase,
  CalendarClock,
  FileText,
  Link2,
  Plus,
  Sparkles,
  Users,
} from "lucide-react";
import {
  fetchAnalyticsData,
  fetchDashboardOverview,
  fetchRecentJobs,
  fetchRecentLeads,
  type AnalyticsData,
  type AnalyticsRange,
  type DashboardOverview,
  type RecentJob,
  type RecentLead,
} from "../../services/dashboardService";
import { fetchInterviewStats, type InterviewStats } from "../../services/interviewsService";
import { formatDate } from "../../utils/date";
import { ApiError } from "../../utils/apiError";
import PageHeader from "../../components/ui/PageHeader";
import PageMeta from "../../components/seo/PageMeta";
import Card from "../../components/ui/Card";
import Button from "../../components/ui/Button";
import Table, { type TableColumn } from "../../components/ui/Table";
import { useLanguage } from "../../contexts/LanguageContext";
import { useChartPalette } from "../../components/charts/chartTheme";
import LineTrendChart from "../../components/charts/LineTrendChart";
import BarComparisonChart, { type BarDatum } from "../../components/charts/BarComparisonChart";
import KpiCard, { type KpiDelta } from "../../components/dashboard/KpiCard";
import SegmentedControl from "../../components/dashboard/SegmentedControl";
import HiringPipeline, { type PipelineStage } from "../../components/dashboard/HiringPipeline";
import RecentActivityList from "../../components/dashboard/RecentActivityList";
import { APPLICATION_STATUS_LABELS, translateOr } from "../../utils/statusLabels";
import type { AnalyticsGroupBy, ApplicationStatus } from "../../types/candidate";

type SectionError = { detail: string | null } | null;

function toSectionError(err: unknown): SectionError {
  return { detail: err instanceof ApiError ? err.message : null };
}

const RANGE_OPTIONS: { value: AnalyticsRange; label: string }[] = [
  { value: "7d", label: "7D" },
  { value: "30d", label: "30D" },
  { value: "90d", label: "90D" },
];

const STATUS_FLOW: ApplicationStatus[] = ["new", "reviewing", "shortlisted", "interview", "hired"];
const STATUS_TERMINAL: ApplicationStatus[] = ["rejected", "withdrawn"];

const LOCALE_MAP: Record<string, string> = {
  en: "en-US",
  ru: "ru-RU",
  uz: "uz-Latn-UZ",
  kiril: "uz-Cyrl-UZ",
};

/** /dashboard — the HR hiring overview: KPIs, trend, pipeline, jobs and activity. */
export default function DashboardPage() {
  const { t, language } = useLanguage();
  const palette = useChartPalette();
  const locale = LOCALE_MAP[language] ?? "en-US";

  const [groupBy, setGroupBy] = useState<AnalyticsGroupBy>("company");
  const [range, setRange] = useState<AnalyticsRange>("30d");
  const [performanceMode, setPerformanceMode] = useState<"byJob" | "bySegment">("byJob");

  const [overview, setOverview] = useState<DashboardOverview | null>(null);
  const [overviewLoading, setOverviewLoading] = useState(true);
  const [overviewError, setOverviewError] = useState<SectionError>(null);

  const [analytics, setAnalytics] = useState<AnalyticsData | null>(null);
  const [analyticsLoading, setAnalyticsLoading] = useState(true);
  const [analyticsError, setAnalyticsError] = useState<SectionError>(null);

  const [recentJobs, setRecentJobs] = useState<RecentJob[]>([]);
  const [recentJobsLoading, setRecentJobsLoading] = useState(true);
  const [recentJobsError, setRecentJobsError] = useState<SectionError>(null);

  const [recentLeads, setRecentLeads] = useState<RecentLead[]>([]);
  const [recentLeadsLoading, setRecentLeadsLoading] = useState(true);
  const [recentLeadsError, setRecentLeadsError] = useState<SectionError>(null);

  const [interviewStats, setInterviewStats] = useState<InterviewStats | null>(null);
  const [interviewStatsLoading, setInterviewStatsLoading] = useState(true);
  const [interviewStatsError, setInterviewStatsError] = useState<SectionError>(null);

  const loadOverview = useCallback((category: AnalyticsGroupBy) => {
    let cancelled = false;
    setOverviewLoading(true);
    setOverviewError(null);
    fetchDashboardOverview(category)
      .then((data) => !cancelled && setOverview(data))
      .catch((err) => !cancelled && setOverviewError(toSectionError(err)))
      .finally(() => !cancelled && setOverviewLoading(false));
    return () => {
      cancelled = true;
    };
  }, []);

  const loadAnalytics = useCallback((selectedRange: AnalyticsRange) => {
    let cancelled = false;
    setAnalyticsLoading(true);
    setAnalyticsError(null);
    fetchAnalyticsData(selectedRange)
      .then((data) => !cancelled && setAnalytics(data))
      .catch((err) => !cancelled && setAnalyticsError(toSectionError(err)))
      .finally(() => !cancelled && setAnalyticsLoading(false));
    return () => {
      cancelled = true;
    };
  }, []);

  const loadRecentJobs = useCallback(() => {
    let cancelled = false;
    setRecentJobsLoading(true);
    setRecentJobsError(null);
    fetchRecentJobs(6)
      .then((data) => !cancelled && setRecentJobs(data))
      .catch((err) => !cancelled && setRecentJobsError(toSectionError(err)))
      .finally(() => !cancelled && setRecentJobsLoading(false));
    return () => {
      cancelled = true;
    };
  }, []);

  const loadRecentLeads = useCallback(() => {
    let cancelled = false;
    setRecentLeadsLoading(true);
    setRecentLeadsError(null);
    fetchRecentLeads(6)
      .then((data) => !cancelled && setRecentLeads(data))
      .catch((err) => !cancelled && setRecentLeadsError(toSectionError(err)))
      .finally(() => !cancelled && setRecentLeadsLoading(false));
    return () => {
      cancelled = true;
    };
  }, []);

  const loadInterviewStats = useCallback(() => {
    let cancelled = false;
    setInterviewStatsLoading(true);
    setInterviewStatsError(null);
    fetchInterviewStats()
      .then((data) => !cancelled && setInterviewStats(data))
      .catch((err) => !cancelled && setInterviewStatsError(toSectionError(err)))
      .finally(() => !cancelled && setInterviewStatsLoading(false));
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => loadOverview(groupBy), [groupBy, loadOverview]);
  useEffect(() => loadAnalytics(range), [range, loadAnalytics]);
  useEffect(() => loadRecentJobs(), [loadRecentJobs]);
  useEffect(() => loadRecentLeads(), [loadRecentLeads]);
  useEffect(() => loadInterviewStats(), [loadInterviewStats]);

  const hasPartialError = Boolean(
    overviewError || analyticsError || recentJobsError || recentLeadsError || interviewStatsError,
  );

  function retryFailedSections() {
    if (overviewError) loadOverview(groupBy);
    if (analyticsError) loadAnalytics(range);
    if (recentJobsError) loadRecentJobs();
    if (recentLeadsError) loadRecentLeads();
    if (interviewStatsError) loadInterviewStats();
  }

  const genericErrorMessage = t("dashboard.error") || "Failed to load.";
  const overviewErrorMessage = overviewError ? overviewError.detail ?? genericErrorMessage : undefined;
  const analyticsErrorMessage = analyticsError ? analyticsError.detail ?? genericErrorMessage : undefined;

  // --- KPI derivations -----------------------------------------------------

  const currentPeriodApplications = useMemo(
    () => (analytics ? analytics.trend.reduce((sum, point) => sum + point.applications, 0) : 0),
    [analytics],
  );
  const previousPeriodApplications = analytics?.previous_period.applications ?? 0;
  const applicationsDelta: KpiDelta | undefined =
    analytics && previousPeriodApplications > 0
      ? {
          value: Math.round(
            (Math.abs(currentPeriodApplications - previousPeriodApplications) / previousPeriodApplications) * 100,
          ),
          direction:
            currentPeriodApplications === previousPeriodApplications
              ? "flat"
              : currentPeriodApplications > previousPeriodApplications
                ? "up"
                : "down",
          comparisonLabel: t("dashboard.kpi.vsPreviousPeriod") || "vs previous period",
        }
      : undefined;

  // Applications nobody has analyzed yet — the one number on this page that
  // asks for an action, so it gets a prompt instead of a passive KPI card.
  const awaitingAnalysisCount = analytics
    ? analytics.analysis_status_counts.new + analytics.analysis_status_counts.pending
    : 0;
  // A brand-new account: show onboarding instead of a wall of zero charts.
  const isFirstRun = !overviewLoading && !overviewError && overview?.total_jobs === 0;

  // --- Trend chart -----------------------------------------------------

  function formatTrendDate(iso: string): string {
    const date = new Date(`${iso}T00:00:00Z`);
    return new Intl.DateTimeFormat(locale, { month: "short", day: "numeric", timeZone: "UTC" }).format(date);
  }

  const trendData = useMemo(
    () => (analytics ? analytics.trend.map((point) => ({ ...point })) : []),
    [analytics],
  );

  // --- Status distribution -> donut + pipeline -----------------------------

  const statusCountMap = useMemo(() => {
    const map = new Map<string, number>();
    analytics?.status_distribution.forEach((row) => map.set(row.status, row.count));
    return map;
  }, [analytics]);

  const statusLabel = useCallback(
    (status: ApplicationStatus) => translateOr(t, `statusMeta.application.${status}`, APPLICATION_STATUS_LABELS[status]),
    [t],
  );

  const pipelineStages: PipelineStage[] = useMemo(
    () =>
      [...STATUS_FLOW, ...STATUS_TERMINAL].map((status) => ({
        status,
        label: statusLabel(status),
        count: statusCountMap.get(status) ?? 0,
        isTerminal: STATUS_TERMINAL.includes(status),
      })),
    [statusCountMap, statusLabel],
  );

  // --- Recruitment performance bar chart -----------------------------------

  const jobBarData: BarDatum[] = useMemo(
    () => (analytics?.top_jobs ?? []).map((job) => ({ key: String(job.job_id), label: job.position, value: job.applications_count })),
    [analytics],
  );
  const segmentBarData: BarDatum[] = useMemo(
    () => (overview?.breakdown ?? []).map((row) => ({ key: row.category, label: row.category, value: row.candidates })),
    [overview],
  );

  const dimensionOptions: { value: AnalyticsGroupBy; label: string }[] = [
    { value: "company", label: t("dashboard.company") || "Company" },
    { value: "position", label: t("dashboard.position") || "Position" },
    { value: "experience", label: t("dashboard.experience") || "Experience" },
  ];

  // --- Recent jobs table -----------------------------------------------------

  const recentJobsColumns: TableColumn<RecentJob>[] = [
    {
      header: t("jobs.position") || "Position",
      render: (job) => (
        <div>
          <Link to={`/jobs/${job.id}`} className="table-primary">
            {job.position}
          </Link>
          <div className="table-secondary">{job.company_name}</div>
        </div>
      ),
    },
    {
      header: t("stats.applications") || "Applications",
      render: (job) => <span className="table-number">{job.leads_count}</span>,
    },
    {
      header: t("dashboard.tableCreated") || "Created",
      render: (job) => <span className="table-muted">{formatDate(job.created_at)}</span>,
      hideOnMobile: true,
    },
    {
      header: "",
      hideOnMobile: true,
      render: (job) => (
        <Link to={`/jobs/${job.id}`} className="link">
          {t("common.view") || "View"}
        </Link>
      ),
      className: "table-actions-cell",
    },
  ];

  return (
    <div className="page">
      <PageMeta title={t("nav.dashboard")} noindex />
      <PageHeader
        title={t("dashboard.title")}
        description={t("dashboard.description")}
        action={
          <>
            {!isFirstRun && (
              <>
                <SegmentedControl value={range} onChange={setRange} options={RANGE_OPTIONS} ariaLabel={t("dashboard.period.label") || "Date range"} />
                <Button variant="secondary" to="/applications">
                  {t("dashboard.viewApplications") || "View Applications"}
                </Button>
              </>
            )}
            <Button to="/jobs/create" icon={<Plus size={16} />}>
              {t("jobs.createJob") || "Create Job"}
            </Button>
          </>
        }
      />

      {hasPartialError && (
        <div
          className="alert alert--warning"
          role="alert"
          style={{ alignItems: "center", justifyContent: "space-between", flexWrap: "wrap" }}
        >
          <span>{t("dashboard.partialErrorMessage") || "Some dashboard data couldn't load."}</span>
          <Button size="sm" variant="secondary" onClick={retryFailedSections}>
            {t("common.retry") || "Retry"}
          </Button>
        </div>
      )}

      {isFirstRun ? (
        <WelcomePanel />
      ) : (
        <>
      <div className="kpi-grid">
        <KpiCard
          label={t("dashboard.kpi.applications") || "Applications"}
          value={currentPeriodApplications}
          hint={t("dashboard.kpi.applicationsHint") || "received in this period"}
          delta={applicationsDelta}
          icon={<FileText size={16} />}
          primary
          loading={analyticsLoading && !analytics}
          errorMessage={analyticsErrorMessage}
        />
        <KpiCard
          label={t("dashboard.kpi.jobs") || "Total Jobs"}
          value={overview?.total_jobs ?? 0}
          hint={t("dashboard.kpi.jobsHint") || "across all vacancies"}
          icon={<Briefcase size={16} />}
          loading={overviewLoading && !overview}
          errorMessage={overviewErrorMessage}
        />
        <KpiCard
          label={t("dashboard.kpi.candidates") || "Candidates"}
          value={analytics?.total_candidates ?? 0}
          hint={t("dashboard.kpi.candidatesHint") || "moved into the hiring pipeline"}
          icon={<Users size={16} />}
          loading={analyticsLoading && !analytics}
          errorMessage={analyticsErrorMessage}
        />
        <KpiCard
          label={t("dashboard.kpi.interviews") || "Upcoming Interviews"}
          value={interviewStats?.upcoming ?? 0}
          hint={
            interviewStats
              ? `${interviewStats.total} ${t("dashboard.kpi.interviewsHint") || "scheduled in total"}`
              : undefined
          }
          icon={<CalendarClock size={16} />}
          loading={interviewStatsLoading && !interviewStats}
          errorMessage={interviewStatsError ? interviewStatsError.detail ?? genericErrorMessage : undefined}
        />
      </div>

      {awaitingAnalysisCount > 0 && (
        <div className="attention-bar" role="status">
          <span className="attention-bar-icon" aria-hidden="true">
            <Sparkles size={16} />
          </span>
          <p className="attention-bar-text">
            {t("dashboard.attention.awaitingAnalysis", { count: awaitingAnalysisCount })}
          </p>
          <Button variant="secondary" size="sm" to="/applications">
            {t("dashboard.attention.action")}
            <ArrowRight size={14} aria-hidden="true" />
          </Button>
        </div>
      )}

      <LineTrendChart
        title={t("dashboard.trend.title") || "Hiring Activity"}
        subtitle={t("dashboard.trend.subtitle") || "Applications and interviews over the selected period"}
        data={trendData}
        xKey="date"
        series={[
          { key: "applications", label: t("stats.applications") || "Applications", color: palette.primary },
          { key: "interviews", label: t("nav.interviews") || "Interviews", color: palette.info },
        ]}
        formatX={formatTrendDate}
        loading={analyticsLoading && !analytics}
        error={analyticsErrorMessage}
        onRetry={() => loadAnalytics(range)}
        emptyTitle={t("dashboard.trend.emptyTitle") || "No activity yet"}
        emptyMessage={
          t("dashboard.trend.emptyMessage") ||
          "Once candidates start applying, your hiring trend will appear here."
        }
      />

      <div className="dashboard-grid dashboard-grid--even">
        <Card
          title={t("dashboard.statusChart.title") || "Application Status"}
          subtitle={t("dashboard.pipelineChart.subtitle") || "Where candidates currently stand"}
        >
          <HiringPipeline
            stages={pipelineStages}
            loading={analyticsLoading && !analytics}
            emptyTitle={t("dashboard.statusChart.emptyTitle") || "No applications yet"}
            emptyMessage={
              t("dashboard.statusChart.emptyMessage") ||
              "Application statuses will appear here once candidates apply."
            }
          />
        </Card>

      <BarComparisonChart
        title={t("dashboard.performance.title") || "Recruitment Performance"}
        action={
          <div style={{ display: "flex", gap: "var(--space-sm)", flexWrap: "wrap" }}>
            <SegmentedControl
              value={performanceMode}
              onChange={setPerformanceMode}
              options={[
                { value: "byJob", label: t("dashboard.performance.byJob") || "By Job" },
                { value: "bySegment", label: t("dashboard.performance.bySegment") || "By Segment" },
              ]}
              ariaLabel={t("dashboard.performance.title") || "Recruitment performance mode"}
            />
            {performanceMode === "bySegment" && (
              <SegmentedControl
                value={groupBy}
                onChange={setGroupBy}
                options={dimensionOptions}
                ariaLabel={t("dashboard.groupBy") || "Grouping dimension"}
                disabled={overviewLoading}
              />
            )}
          </div>
        }
        data={performanceMode === "byJob" ? jobBarData : segmentBarData}
        valueLabel={t("stats.applications") || "Applications"}
        loading={performanceMode === "byJob" ? analyticsLoading && !analytics : overviewLoading && !overview}
        error={performanceMode === "byJob" ? analyticsErrorMessage : overviewErrorMessage}
        onRetry={performanceMode === "byJob" ? () => loadAnalytics(range) : () => loadOverview(groupBy)}
        emptyTitle={t("dashboard.performance.emptyTitle") || "No data yet"}
        emptyMessage={
          t("dashboard.performance.emptyMessage") ||
          "Create a job and start receiving applications to see this chart."
        }
      />
      </div>

      <div className="dashboard-grid dashboard-grid--even">
        <Card
          title={t("dashboard.recentJobs") || "Recent Jobs"}
          action={
            <Link className="link" to="/jobs">
              {t("dashboard.viewAll") || "View all"}
            </Link>
          }
          flush
        >
          <Table
            columns={recentJobsColumns}
            rows={recentJobs}
            rowKey={(job) => job.id}
            loading={recentJobsLoading && recentJobs.length === 0}
            loadingRows={4}
            emptyState={
              recentJobsError ? (
                <div className="chart-state">
                  <p className="error-state-message">{recentJobsError.detail ?? genericErrorMessage}</p>
                  <Button size="sm" onClick={loadRecentJobs}>
                    {t("common.retry") || "Retry"}
                  </Button>
                </div>
              ) : (
                <div className="chart-state">
                  <p className="muted-note">{t("dashboard.noJobs") || "No jobs yet."}</p>
                </div>
              )
            }
          />
        </Card>

        <Card
          title={t("dashboard.activity.title") || "Recent Activity"}
          action={
            <Link className="link" to="/candidates">
              {t("dashboard.viewAll") || "View all"}
            </Link>
          }
        >
          <RecentActivityList
            jobs={recentJobs}
            leads={recentLeads}
            loading={(recentJobsLoading && recentJobs.length === 0) || (recentLeadsLoading && recentLeads.length === 0)}
            jobLabel={t("dashboard.activity.jobCreated") || "Job created"}
            applicationLabel={t("dashboard.activity.newApplication") || "New application"}
            emptyTitle={t("dashboard.activity.emptyTitle") || "No recent activity"}
            emptyMessage={t("dashboard.activity.emptyMessage") || "Recent jobs and applications will show up here."}
          />
        </Card>
      </div>

        </>
      )}
    </div>
  );
}

/**
 * First-run state for an account with no jobs: explains the three steps of the
 * workflow and offers the one action that starts it.
 */
function WelcomePanel() {
  const { t } = useLanguage();
  const steps = [
    { icon: <Briefcase size={18} />, title: t("dashboard.welcome.step1Title"), text: t("dashboard.welcome.step1Text") },
    { icon: <Link2 size={18} />, title: t("dashboard.welcome.step2Title"), text: t("dashboard.welcome.step2Text") },
    { icon: <Sparkles size={18} />, title: t("dashboard.welcome.step3Title"), text: t("dashboard.welcome.step3Text") },
  ];
  return (
    <section className="card welcome-panel" aria-labelledby="welcome-title">
      <h2 id="welcome-title" className="welcome-title">{t("dashboard.welcome.title")}</h2>
      <p className="welcome-text">{t("dashboard.welcome.text")}</p>
      <ol className="welcome-steps">
        {steps.map((step, index) => (
          <li key={index} className="welcome-step">
            <span className="welcome-step-icon" aria-hidden="true">{step.icon}</span>
            <span className="welcome-step-number" aria-hidden="true">{index + 1}</span>
            <strong>{step.title}</strong>
            <span>{step.text}</span>
          </li>
        ))}
      </ol>
      <Button to="/jobs/create" size="lg" icon={<Plus size={16} />}>
        {t("dashboard.welcome.cta")}
      </Button>
    </section>
  );
}
