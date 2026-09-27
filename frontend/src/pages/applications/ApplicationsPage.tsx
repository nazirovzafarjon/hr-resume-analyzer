import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Search, Sparkles } from "lucide-react";
import { fetchApplications } from "../../services/workersService";
import { fetchJobs } from "../../services/jobsService";
import { formatDate } from "../../utils/date";
import PageHeader from "../../components/ui/PageHeader";
import PageMeta from "../../components/seo/PageMeta";
import Button from "../../components/ui/Button";
import Card from "../../components/ui/Card";
import EmptyState from "../../components/ui/EmptyState";
import StatCard from "../../components/ui/StatCard";
import Table, { type TableColumn } from "../../components/ui/Table";
import { SkeletonTable } from "../../components/ui/Skeleton";
import ApplicationStatusBadge, { AnalysisStatusBadge } from "../../components/ui/ApplicationStatusBadge";
import AutoAnalyzeModal from "../../components/applications/AutoAnalyzeModal";
import { useLanguage } from "../../contexts/LanguageContext";
import { scoreTone } from "../../utils/statusLabels";
import { getErrorMessage } from "../../utils/apiError";
import type { Candidate, ApplicationStatus } from "../../types/worker";
import type { JobInput } from "../../types/job";

const STATUS_FILTERS: ApplicationStatus[] = [
  "new",
  "reviewing",
  "shortlisted",
  "interview",
  "rejected",
  "withdrawn",
];

/**
 * /applications — the HR review desk.
 *
 * Answers three questions at a glance: who applied, what the AI thinks of them,
 * and where the application currently sits. Summary cards on top, then a
 * filterable table ordered so the most actionable rows are easy to scan.
 */
export default function ApplicationsPage() {
  const { t } = useLanguage();
  const [applications, setApplications] = useState<Candidate[]>([]);
  const [jobs, setJobs] = useState<JobInput[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [search, setSearch] = useState("");
  const [jobFilter, setJobFilter] = useState("all");
  const [statusFilter, setStatusFilter] = useState<ApplicationStatus | "all">("all");
  const [autoAnalyzeOpen, setAutoAnalyzeOpen] = useState(false);
  const [selectedJobId, setSelectedJobId] = useState<number | undefined>();

  useEffect(() => {
    let cancelled = false;
    async function loadData() {
      setLoading(true);
      setError(null);
      try {
        const [appsData, jobsData] = await Promise.all([
          fetchApplications(),
          fetchJobs().catch(() => [] as JobInput[]),
        ]);
        if (!cancelled) {
          setApplications(appsData);
          setJobs(jobsData);
        }
      } catch (err) {
        if (!cancelled) setError(getErrorMessage(err, t("errors.loadMessage")));
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    loadData();
    return () => {
      cancelled = true;
    };
  }, [t]);

  const stats = useMemo(() => {
    const count = (status: ApplicationStatus) =>
      applications.filter((app) => app.application_status === status).length;
    return {
      total: applications.length,
      fresh: count("new"),
      reviewing: count("reviewing"),
      shortlisted: count("shortlisted"),
    };
  }, [applications]);

  const filtered = useMemo(() => {
    const query = search.trim().toLowerCase();
    return applications.filter((app) => {
      const matchesSearch =
        !query ||
        app.name.toLowerCase().includes(query) ||
        app.email.toLowerCase().includes(query) ||
        app.position.toLowerCase().includes(query) ||
        app.company_name.toLowerCase().includes(query);
      const matchesJob = jobFilter === "all" || String(app.job_id) === jobFilter;
      const matchesStatus =
        statusFilter === "all" || app.application_status === statusFilter;
      return matchesSearch && matchesJob && matchesStatus;
    });
  }, [applications, search, jobFilter, statusFilter]);

  const columns = useMemo<TableColumn<Candidate>[]>(() => buildColumns(t), [t]);


  return (
    <div className="page">
      <PageMeta title={t("nav.applications")} noindex />
      <PageHeader
        title={t("applications.title")}
        description={t("applications.description")}
        action={
          <Button
            icon={<Sparkles size={16} />}
            onClick={() => {
              setSelectedJobId(jobFilter !== "all" ? Number(jobFilter) : undefined);
              setAutoAnalyzeOpen(true);
            }}
          >
            {t("applications.autoAnalyze")}
          </Button>
        }
      />

      <div className="stat-grid">
        <StatCard label={t("appStats.total")} value={stats.total} hint={t("appStats.totalHint")} tone="info" />
        <StatCard label={t("appStats.fresh")} value={stats.fresh} hint={t("appStats.freshHint")} tone="warning" />
        <StatCard label={t("appStats.reviewing")} value={stats.reviewing} hint={t("appStats.reviewingHint")} />
        <StatCard
          label={t("appStats.shortlisted")}
          value={stats.shortlisted}
          hint={t("appStats.shortlistedHint")}
          tone="success"
        />
      </div>

      <Card flush>
        <div className="candidate-toolbar" style={{ padding: "var(--space-xl) var(--space-xl) 0" }}>
          <label className="toolbar-label toolbar-label--grow">
            {t("common.search")}
            <span className="search-field">
              <span className="search-field-icon" aria-hidden="true">
                <Search size={15} />
              </span>
              <input
                className="field-input"
                type="search"
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder={t("searchPlaceholder")}
                aria-label={t("searchPlaceholder")}
              />
            </span>
          </label>

          <label className="toolbar-label">
            {t("nav.jobs")}
            <select
              className="field-select"
              value={jobFilter}
              onChange={(event) => setJobFilter(event.target.value)}
            >
              <option value="all">{t("allJobs")}</option>
              {jobs.map((job) => (
                <option key={job.id} value={String(job.id)}>
                  {job.company_name} — {job.position}
                </option>
              ))}
            </select>
          </label>

          <label className="toolbar-label">
            {t("labels.status")}
            <select
              className="field-select"
              value={statusFilter}
              onChange={(event) =>
                setStatusFilter(event.target.value as ApplicationStatus | "all")
              }
            >
              <option value="all">{t("applications.status.all")}</option>
              {STATUS_FILTERS.map((status) => (
                <option key={status} value={status}>
                  {t(`statusMeta.application.${status}`)}
                </option>
              ))}
            </select>
          </label>
        </div>

        {loading ? (
          <SkeletonTable rows={6} columns={5} />
        ) : error ? (
          <EmptyState
            tone="error"
            title={t("errors.loadTitle")}
            message={error}
            action={
              <Button variant="secondary" onClick={() => window.location.reload()}>
                {t("common.retry")}
              </Button>
            }
          />
        ) : applications.length === 0 ? (
          <EmptyState title={t("empty.applicationsTitle")} message={t("empty.applicationsMessage")} />
        ) : filtered.length === 0 ? (
          <EmptyState title={t("empty.noMatchingTitle")} message={t("empty.noMatchingMessage")} />
        ) : (
          <Table rows={filtered} rowKey={(app) => app.id} columns={columns} caption={t("applications.title")} />
        )}
      </Card>

      <AutoAnalyzeModal
        open={autoAnalyzeOpen}
        onClose={() => setAutoAnalyzeOpen(false)}
        jobId={selectedJobId}
      />
    </div>
  );
}
function buildColumns(t: (key: string) => string): TableColumn<Candidate>[] {
  return [
    {
      header: t("applications.candidate"),
      sort: (a, b) => a.name.localeCompare(b.name),
      render: (app) => (
        <div>
          <Link className="table-primary" to={`/applications/${app.id}`}>
            {app.name}
          </Link>
          <div className="table-secondary">{app.email}</div>
        </div>
      ),
    },
    {
      header: t("applications.position"),
      render: (app) => (
        <div>
          <div className="table-primary">{app.position || "—"}</div>
          <div className="table-secondary">{app.company_name || "—"}</div>
        </div>
      ),
    },
    {
      header: t("applications.aiMatch"),
      sort: (a, b) => (a.ai_score || 0) - (b.ai_score || 0),
      render: (app) => {
        if (app.analysis_status === "analyzing") {
          return <span className="table-muted">{t("statusMeta.analysis.analyzing")}</span>;
        }
        const tone = scoreTone(app.analysis_status === "completed" ? app.ai_score : null);
        if (tone === "empty") return <span className="table-muted">—</span>;
        return (
          <span className={`score-pill score-pill--${tone}`}>{Math.round(app.ai_score)}%</span>
        );
      },
    },
    {
      header: t("applications.aiStatusColumn"),
      render: (app) => <AnalysisStatusBadge value={app.analysis_status} />,
    },
    {
      header: t("applications.applicationStatus"),
      render: (app) => <ApplicationStatusBadge value={app.application_status} />,
    },
    {
      header: t("applications.submitted"),
      sort: (a, b) => (a.submitted_at || "").localeCompare(b.submitted_at || ""),
      render: (app) => (
        <span className="table-muted">{formatDate(app.submitted_at || app.created_at)}</span>
      ),
    },
    {
      header: t("labels.actions"),
      headerClassName: "table-actions-cell",
      className: "table-actions-cell",
      render: (app) => (
        <Link className="row-action" to={`/applications/${app.id}`}>
          {t("applications.view")}
        </Link>
      ),
    },
  ];
}
