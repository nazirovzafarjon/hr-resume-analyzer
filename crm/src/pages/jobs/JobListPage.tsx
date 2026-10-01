import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  Copy,
  Eye,
  ExternalLink,
  MoreHorizontal,
  Pencil,
  Plus,
  Trash2,
  Users,
} from "lucide-react";
import { fetchJobs, deleteJob as deleteJobApi } from "../../services/jobsService";
import { formatDate } from "../../utils/date";
import { copyToClipboard } from "../../utils/clipboard";
import { jobStatusFromToken } from "../../utils/statusLabels";
import { applicationUrl } from "../../components/application-form/ApplicationLinkCard";
import PageHeader from "../../components/ui/PageHeader";
import PageMeta from "../../components/seo/PageMeta";
import Button from "../../components/ui/Button";
import Card from "../../components/ui/Card";
import FilterBar from "../../components/ui/FilterBar";
import EmptyState from "../../components/ui/EmptyState";
import ConfirmDialog from "../../components/ui/ConfirmDialog";
import StatusBadge from "../../components/ui/StatusBadge";
import Dropdown, { DropdownItem, DropdownSeparator } from "../../components/ui/Dropdown";
import Table, { type TableColumn } from "../../components/ui/Table";
import { ExportButton } from "../../components/exports/ExportButton";
import { ExportModal } from "../../components/exports/ExportModal";
import { useLanguage } from "../../contexts/LanguageContext";
import { useNotify } from "../../contexts/ToastContext";
import { getErrorMessage } from "../../utils/apiError";
import type { JobInput } from "../../types/job";

type SortKey = "newest" | "leads" | "company";

const PAGE_SIZE = 20;

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
  const navigate = useNavigate();

  const [jobs, setJobs] = useState<JobInput[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [companyFilter, setCompanyFilter] = useState("all");
  const [positionFilter, setPositionFilter] = useState("all");
  const [sortKey, setSortKey] = useState<SortKey>("newest");
  const [deleteTarget, setDeleteTarget] = useState<number | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [exportModalOpen, setExportModalOpen] = useState(false);

  function loadJobs() {
    let cancelled = false;
    setLoading(true);
    setError(null);
    fetchJobs()
      .then((data) => !cancelled && setJobs(data))
      .catch((err) => !cancelled && setError(getErrorMessage(err, t("errors.loadMessage"))))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }

  useEffect(() => loadJobs(), []); // eslint-disable-line react-hooks/exhaustive-deps

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
        default: {
          const delta = new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
          return delta !== 0 ? delta : b.id - a.id;
        }
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

  async function handleCopyLink(job: JobInput) {
    const token = job.application_form?.public_token;
    if (!token) return;
    const ok = await copyToClipboard(applicationUrl(token));
    if (ok) {
      notify.success(t("applicationForm.link.copiedToast") || "Link copied");
    } else {
      notify.error(t("applicationForm.link.copyFailedToast") || "Couldn't copy the link");
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
      {
        header: t("labels.status") || "Status",
        render: (job) => <StatusBadge kind="job" value={jobStatusFromToken(job.application_form?.public_token)} />,
      },
      {
        header: t("jobs.leads"),
        sort: (a, b) => a.leads_count - b.leads_count,
        render: (job) => <span className="table-number">{job.leads_count}</span>,
      },
      {
        header: t("jobs.created"),
        sort: (a, b) => a.created_at.localeCompare(b.created_at),
        hideOnMobile: true,
        render: (job) => <span className="table-muted">{formatDate(job.created_at)}</span>,
      },
      {
        header: t("jobs.actions"),
        headerClassName: "table-actions-cell",
        className: "table-actions-cell",
        render: (job) => {
          const published = Boolean(job.application_form?.public_token);
          return (
            <Dropdown
              trigger={({ toggle, id }) => (
                <button
                  type="button"
                  className="row-action row-action--icon"
                  id={id}
                  onClick={toggle}
                  aria-label={
                    t("jobs.rowActionsAriaLabel", { position: job.position }) ||
                    `Actions for ${job.position}`
                  }
                >
                  <MoreHorizontal size={16} />
                </button>
              )}
            >
              <DropdownItem icon={<Eye size={14} />} onClick={() => navigate(`/jobs/${job.id}`)}>
                {t("jobs.view")}
              </DropdownItem>
              <DropdownItem icon={<Pencil size={14} />} onClick={() => navigate(`/jobs/${job.id}/edit`)}>
                {t("jobs.edit")}
              </DropdownItem>
              <DropdownItem icon={<Users size={14} />} onClick={() => navigate(`/applications?job=${job.id}`)}>
                {t("jobs.viewApplications") || "View Applications"}
              </DropdownItem>
              {published && (
                <>
                  <DropdownSeparator />
                  <DropdownItem icon={<Copy size={14} />} onClick={() => handleCopyLink(job)}>
                    {t("jobs.copyPublicLink") || "Copy Public Link"}
                  </DropdownItem>
                  <DropdownItem
                    icon={<ExternalLink size={14} />}
                    onClick={() => window.open(applicationUrl(job.application_form!.public_token), "_blank", "noreferrer")}
                  >
                    {t("jobs.openPublicLink") || "Open Public Link"}
                  </DropdownItem>
                </>
              )}
              <DropdownSeparator />
              <DropdownItem icon={<Trash2 size={14} />} danger onClick={() => setDeleteTarget(job.id)}>
                {t("jobs.delete")}
              </DropdownItem>
            </Dropdown>
          );
        },
      },
    ],
    [t, navigate], // eslint-disable-line react-hooks/exhaustive-deps
  );

  const clearFilters = () => {
    setSearch("");
    setCompanyFilter("all");
    setPositionFilter("all");
  };

  const hasActiveFilters = search.trim() !== "" || companyFilter !== "all" || positionFilter !== "all";

  return (
    <div className="page">
      <PageMeta title={t("nav.jobs")} noindex />
      <PageHeader
        title={t("jobs.title")}
        description={t("jobs.pageDescription") || "Manage your job vacancies"}
        action={
          <Button to="/jobs/create" icon={<Plus size={16} />}>
            {t("jobs.createJob")}
          </Button>
        }
      />

      <Card flush>
        <FilterBar
          search={{ value: search, onChange: setSearch, placeholder: t("jobs.searchPlaceholder") }}
          active={hasActiveFilters}
          onClear={clearFilters}
        >
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

          <ExportButton onClick={() => setExportModalOpen(true)} disabled={jobs.length === 0} />
        </FilterBar>

        <Table
          rows={filteredJobs}
          pageSize={PAGE_SIZE}
          rowKey={(job) => job.id}
          columns={columns}
          caption={t("jobs.title")}
          loading={loading}
          loadingRows={6}
          emptyState={
            error ? (
              <EmptyState
                tone="error"
                title={t("errors.loadTitle")}
                message={error}
                action={
                  <Button variant="secondary" onClick={loadJobs}>
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
            ) : (
              <EmptyState
                title={t("empty.noMatchingTitle")}
                message={t("empty.noMatchingMessage")}
                action={
                  <Button variant="secondary" onClick={clearFilters} disabled={!hasActiveFilters}>
                    {t("jobs.clearFilters") || "Clear filters"}
                  </Button>
                }
              />
            )
          }
        />

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
        loading={deleting}
      />

      <ExportModal
        open={exportModalOpen}
        onClose={() => setExportModalOpen(false)}
        resource="jobs"
        companies={companies}
        defaultFilters={{
          company: companyFilter !== "all" ? companyFilter : undefined,
        }}
      />
    </div>
  );
}
