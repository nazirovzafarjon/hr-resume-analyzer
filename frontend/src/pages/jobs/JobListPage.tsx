import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Plus, Search } from "lucide-react";
import { fetchJobs, deleteJob as deleteJobApi } from "../../services/jobsService";
import { formatDate } from "../../utils/date";
import PageHeader from "../../components/ui/PageHeader";
import Button from "../../components/ui/Button";
import Card from "../../components/ui/Card";
import EmptyState from "../../components/ui/EmptyState";
import ConfirmDialog from "../../components/ui/ConfirmDialog";
import Table, { type TableColumn } from "../../components/ui/Table";
import { SkeletonTable } from "../../components/ui/Skeleton";
import { useLanguage } from "../../contexts/LanguageContext";
import { useNotify } from "../../contexts/ToastContext";
import { getErrorMessage } from "../../utils/apiError";
import type { JobInput } from "../../types/job";

type SortKey = "newest" | "leads" | "company";

/**
 * /jobs — search, filter and manage job vacancies.
 *
 * The job list opens the recruitment workflow, so the page leads with one
 * primary action (Create job) and keeps every other control (search, filters,
 * sorting) in a single toolbar above the table.
 */
export default function JobListPage() {
  const { t } = useLanguage();
  const notify = useNotify();

  const [jobs, setJobs] = useState<JobInput[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [companyFilter, setCompanyFilter] = useState("all");
  const [positionFilter, setPositionFilter] = useState("all");
  const [sortKey, setSortKey] = useState<SortKey>("newest");
  const [deleteTarget, setDeleteTarget] = useState<number | null>(null);
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    let mounted = true;
    async function loadJobs() {
      setLoading(true);
      setError(null);
      try {
        const data = await fetchJobs();
        if (mounted) setJobs(data);
      } catch (err) {
        if (mounted) setError(getErrorMessage(err, t("errors.loadMessage")));
      } finally {
        if (mounted) setLoading(false);
      }
    }
    loadJobs();
    return () => {
      mounted = false;
    };
  }, [t]);

  const companies = useMemo(
    () => Array.from(new Set(jobs.map((job) => job.company_name))).sort(),
    [jobs],
  );
  const positions = useMemo(
    () => Array.from(new Set(jobs.map((job) => job.position))).sort(),
    [jobs],
  );

  const filteredJobs = useMemo(() => {
    const query = search.trim().toLowerCase();
    const filtered = jobs.filter((job) => {
      const matchesSearch =
        !query ||
        job.company_name.toLowerCase().includes(query) ||
        job.position.toLowerCase().includes(query);
      const matchesCompany = companyFilter === "all" || job.company_name === companyFilter;
      const matchesPosition = positionFilter === "all" || job.position === positionFilter;
      return matchesSearch && matchesCompany && matchesPosition;
    });

    return filtered.sort((a, b) => {
      switch (sortKey) {
        case "leads":
          return b.leads_count - a.leads_count;
        case "company":
          return a.company_name.localeCompare(b.company_name);
        case "newest":
        default:
          return b.created_at < a.created_at ? -1 : 1;
      }
    });
  }, [jobs, search, companyFilter, positionFilter, sortKey]);

  const deleteTargetJob = jobs.find((job) => job.id === deleteTarget);

  async function handleConfirmDelete() {
    if (deleteTarget === null) return;

    setDeleting(true);
    try {
      await deleteJobApi(deleteTarget);
      setJobs((current) => current.filter((job) => job.id !== deleteTarget));
      notify.success(t("toast.jobDeleted"), deleteTargetJob?.position);
      setDeleteTarget(null);
    } catch (err) {
      notify.error(t("toast.deleteFailed"), getErrorMessage(err));
    } finally {
      setDeleting(false);
    }
  }

  const columns = useMemo<TableColumn<JobInput>[]>(
    () => [
      {
        header: t("jobs.position"),
        sort: (a, b) => a.position.localeCompare(b.position),
        render: (job) => (
          <div>
            <Link className="table-primary" to={`/jobs/${job.id}`}>
              {job.position}
            </Link>
            <div className="table-secondary">{job.company_name}</div>
          </div>
        ),
      },
      { header: t("jobs.experience"), render: (job) => job.required_experience || "—" },
      {
        header: t("jobs.skills"),
        render: (job) => <span className="table-muted">{job.required_skills || "—"}</span>,
      },
      {
        header: t("jobs.leads"),
        sort: (a, b) => a.leads_count - b.leads_count,
        headerClassName: "table-actions-cell",
        render: (job) => <span className="table-number">{job.leads_count}</span>,
      },
      {
        header: t("jobs.created"),
        sort: (a, b) => a.created_at.localeCompare(b.created_at),
        render: (job) => <span className="table-muted">{formatDate(job.created_at)}</span>,
      },
      {
        header: t("jobs.actions"),
        headerClassName: "table-actions-cell",
        render: (job) => (
          <div className="row-actions">
            <Link className="row-action" to={`/jobs/${job.id}`}>
              {t("jobs.view")}
            </Link>
            <Link className="row-action" to={`/jobs/${job.id}/edit`}>
              {t("jobs.edit")}
            </Link>
            <button
              type="button"
              className="row-action row-action--danger"
              onClick={() => setDeleteTarget(job.id)}
              disabled={deleting}
            >
              {t("jobs.delete")}
            </button>
          </div>
        ),
      },
    ],
    [t, deleting],
  );

  const clearFilters = () => {
    setSearch("");
    setCompanyFilter("all");
    setPositionFilter("all");
  };

  return (
    <div className="page">
      <PageHeader
        title={t("jobs.title")}
        description={t("jobs.description")}
        action={
          <Button to="/jobs/create" icon={<Plus size={16} />}>
            {t("jobs.createJob")}
          </Button>
        }
      />

      <Card flush>
        <div className="toolbar" style={{ padding: "var(--space-xl) var(--space-xl) 0" }}>
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
                placeholder={t("jobs.searchPlaceholder")}
                aria-label={t("jobs.searchPlaceholder")}
              />
            </span>
          </label>

          <label className="toolbar-label">
            {t("jobs.company")}
            <select
              className="field-select"
              value={companyFilter}
              onChange={(event) => setCompanyFilter(event.target.value)}
            >
              <option value="all">{t("jobs.allCompanies")}</option>
              {companies.map((company) => (
                <option key={company} value={company}>
                  {company}
                </option>
              ))}
            </select>
          </label>

          <label className="toolbar-label">
            {t("jobs.position")}
            <select
              className="field-select"
              value={positionFilter}
              onChange={(event) => setPositionFilter(event.target.value)}
            >
              <option value="all">{t("jobs.allPositions")}</option>
              {positions.map((position) => (
                <option key={position} value={position}>
                  {position}
                </option>
              ))}
            </select>
          </label>

          <label className="toolbar-label">
            {t("common.sort")}
            <select
              className="field-select"
              value={sortKey}
              onChange={(event) => setSortKey(event.target.value as SortKey)}
            >
              <option value="newest">{t("jobs.newestFirst")}</option>
              <option value="leads">{t("jobs.mostLeads")}</option>
              <option value="company">{t("jobs.companyAZ")}</option>
            </select>
          </label>
        </div>

        {loading ? (
          <SkeletonTable rows={5} columns={4} />
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
        ) : jobs.length === 0 ? (
          <EmptyState
            title={t("empty.jobsTitle")}
            message={t("empty.jobsMessage")}
            action={
              <Button to="/jobs/create" icon={<Plus size={16} />}>
                {t("jobs.createJob")}
              </Button>
            }
          />
        ) : filteredJobs.length === 0 ? (
          <EmptyState
            title={t("empty.noMatchingTitle")}
            message={t("empty.noMatchingMessage")}
            action={
              <Button variant="secondary" onClick={clearFilters}>
                {t("common.filters")}
              </Button>
            }
          />
        ) : (
          <Table
            rows={filteredJobs}
            rowKey={(job) => job.id}
            columns={columns}
            caption={t("jobs.title")}
          />
        )}
      </Card>

      <ConfirmDialog
        open={deleteTarget !== null}
        title={t("jobs.deleteConfirm")}
        message={
          deleteTargetJob
            ? `${t("jobs.deleteConfirmMessage")} — "${deleteTargetJob.position}" (${deleteTargetJob.company_name})`
            : t("jobs.deleteConfirmMessage")
        }
        confirmLabel={t("jobs.deleteJobBtn")}
        cancelLabel={t("common.cancel")}
        onConfirm={handleConfirmDelete}
        onCancel={() => setDeleteTarget(null)}
        disabled={deleting}
      />
    </div>
  );
}
