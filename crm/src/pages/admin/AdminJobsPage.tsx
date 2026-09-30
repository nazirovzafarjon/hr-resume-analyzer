import { useCallback, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { Eye, Pencil, Plus, Trash2 } from "lucide-react";
import PageHeader from "../../components/ui/PageHeader";
import PageMeta from "../../components/seo/PageMeta";
import Button from "../../components/ui/Button";
import Card from "../../components/ui/Card";
import ConfirmDialog from "../../components/ui/ConfirmDialog";
import EmptyState from "../../components/ui/EmptyState";
import FilterBar from "../../components/ui/FilterBar";
import Modal from "../../components/ui/Modal";
import { SkeletonText } from "../../components/ui/Skeleton";
import { ApplicationStatusBadge } from "../../components/ui/ApplicationStatusBadge";
import ServerTable from "../../components/admin/ServerTable";
import {
  CompanySelect,
  DateRangeFields,
  OwnerSelect,
  nextSort,
  useSearchInput,
} from "../../components/admin/filters";
import type { TableColumn } from "../../components/ui/Table";
import { useLanguage } from "../../contexts/LanguageContext";
import { useNotify } from "../../contexts/ToastContext";
import { useApiQuery } from "../../hooks/useApiQuery";
import { useUrlFilters } from "../../hooks/useUrlFilters";
import { deleteAdminJob, fetchAdminJob, fetchAdminJobs } from "../../services/adminService";
import { getErrorMessage } from "../../utils/apiError";
import { formatDate } from "../../utils/date";
import type { AdminJobRow } from "../../types/admin";
import { parseId } from "./adminFormat";

const DEFAULTS = {
  q: "",
  owner_id: "",
  company: "",
  date_from: "",
  date_to: "",
  sort: "created_at",
  order: "desc",
};

const PAGE_SIZE = 25;

export default function AdminJobsPage() {
  const { t } = useLanguage();
  const notify = useNotify();
  const { values, page, setFilters, setPage, clear, active } = useUrlFilters(DEFAULTS);
  const commitSearch = useCallback((q: string) => setFilters({ q }), [setFilters]);
  const [search, setSearch] = useSearchInput(values.q, commitSearch);
  const [searchParams, setSearchParams] = useSearchParams();
  const openJobId = parseId(searchParams.get("job"));
  const [toDelete, setToDelete] = useState<AdminJobRow | null>(null);
  const [deleting, setDeleting] = useState(false);

  const params = { ...values, page, limit: PAGE_SIZE };
  const query = useApiQuery(() => fetchAdminJobs(params), JSON.stringify(params));

  // The detail dialog is addressable (`?job=12`) so audit log and user pages
  // can link straight to a job.
  const openJob = useCallback(
    (id: number | null) =>
      setSearchParams((current) => {
        const next = new URLSearchParams(current);
        if (id) next.set("job", String(id));
        else next.delete("job");
        return next;
      }),
    [setSearchParams],
  );

  async function confirmDelete() {
    if (!toDelete) return;
    setDeleting(true);
    try {
      await deleteAdminJob(toDelete.id);
      notify.success(t("admin.jobs.deleted", { name: toDelete.position }));
      setToDelete(null);
      openJob(null);
      query.reload();
    } catch (error) {
      notify.error(t("admin.jobs.deleteFailed"), getErrorMessage(error));
    } finally {
      setDeleting(false);
    }
  }

  const columns = useMemo<TableColumn<AdminJobRow>[]>(
    () => [
      {
        header: t("admin.jobs.job"),
        sortKey: "position",
        render: (row) => (
          <div>
            <button type="button" className="table-primary link-button" onClick={() => openJob(row.id)}>
              {row.position}
            </button>
            <div className="table-secondary">{row.company_name}</div>
          </div>
        ),
      },
      {
        header: t("admin.jobs.owner"),
        render: (row) => (
          <div>
            <Link className="table-primary" to={`/admin/users/${row.owner_id}`}>
              {row.owner_name}
            </Link>
            <div className="table-secondary">{row.owner_email}</div>
          </div>
        ),
      },
      {
        header: t("admin.jobs.applications"),
        sortKey: "applications",
        className: "table-number",
        render: (row) => (
          <Link to={`/admin/applications?job_id=${row.id}`}>{row.applications_count}</Link>
        ),
      },
      {
        header: t("admin.jobs.candidates"),
        className: "table-number",
        hideOnMobile: true,
        render: (row) => row.candidates_count,
      },
      {
        header: t("admin.jobs.analyzed"),
        className: "table-number",
        hideOnMobile: true,
        render: (row) => row.analyzed_count,
      },
      {
        header: t("admin.jobs.created"),
        sortKey: "created_at",
        hideOnMobile: true,
        render: (row) => <span className="table-muted admin-nowrap">{formatDate(row.created_at)}</span>,
      },
      {
        header: t("labels.actions"),
        headerClassName: "table-actions-cell",
        className: "table-actions-cell",
        render: (row) => (
          <span className="row-actions">
            <button
              type="button"
              className="row-action row-action--icon"
              title={t("admin.common.view")}
              aria-label={`${t("admin.common.view")}: ${row.position}`}
              onClick={() => openJob(row.id)}
            >
              <Eye size={15} aria-hidden="true" />
            </button>
            {/* Admins have every HR permission: edit in the hiring workspace. */}
            <Link
              className="row-action row-action--icon"
              title={t("admin.common.manage")}
              aria-label={`${t("admin.common.manage")}: ${row.position}`}
              to={`/jobs/${row.id}`}
            >
              <Pencil size={15} aria-hidden="true" />
            </Link>
            <button
              type="button"
              className="row-action row-action--icon row-action--danger"
              title={t("admin.jobs.delete")}
              aria-label={`${t("admin.jobs.delete")}: ${row.position}`}
              onClick={() => setToDelete(row)}
            >
              <Trash2 size={15} aria-hidden="true" />
            </button>
          </span>
        ),
      },
    ],
    [t, openJob],
  );

  return (
    <div className="page">
      <PageMeta title={t("admin.nav.jobs")} noindex />
      <PageHeader
        title={t("admin.jobs.title")}
        description={t("admin.jobs.description")}
        action={
          <Button icon={<Plus size={15} />} to="/jobs/create">
            {t("admin.jobs.create")}
          </Button>
        }
      />

      <Card flush>
        <FilterBar
          search={{ value: search, onChange: setSearch, placeholder: t("admin.jobs.searchPlaceholder") }}
          active={active}
          onClear={clear}
        >
          <OwnerSelect value={values.owner_id} onChange={(owner_id) => setFilters({ owner_id })} />
          <CompanySelect value={values.company} onChange={(company) => setFilters({ company })} />
          <DateRangeFields from={values.date_from} to={values.date_to} onChange={setFilters} />
        </FilterBar>

        <ServerTable
          columns={columns}
          data={query.data}
          loading={query.loading}
          error={query.error}
          onRetry={query.reload}
          rowKey={(row) => row.id}
          caption={t("admin.jobs.title")}
          onPageChange={setPage}
          sort={{ key: values.sort, order: values.order as "asc" | "desc" }}
          onSortChange={(key) => setFilters(nextSort(values, key))}
          filtered={active}
          onClearFilters={clear}
          emptyTitle={t("admin.jobs.emptyTitle")}
          emptyMessage={t("admin.jobs.emptyMessage")}
        />
      </Card>

      {openJobId && (
        <JobDetailModal
          jobId={openJobId}
          onClose={() => openJob(null)}
          onDelete={(job) => setToDelete(job)}
        />
      )}

      <ConfirmDialog
        open={toDelete !== null}
        title={t("admin.jobs.deleteTitle")}
        message={t("admin.jobs.deleteMessage", {
          name: toDelete?.position ?? "",
          owner: toDelete?.owner_email ?? "",
          count: toDelete?.applications_count ?? 0,
        })}
        confirmLabel={t("admin.jobs.delete")}
        cancelLabel={t("common.cancel")}
        loading={deleting}
        onConfirm={confirmDelete}
        onCancel={() => setToDelete(null)}
      />
    </div>
  );
}

function JobDetailModal({
  jobId,
  onClose,
  onDelete,
}: {
  jobId: number;
  onClose: () => void;
  onDelete: (job: AdminJobRow) => void;
}) {
  const { t } = useLanguage();
  const { data: job, loading, error, reload } = useApiQuery(() => fetchAdminJob(jobId), String(jobId));

  return (
    <Modal
      open
      size="lg"
      title={job?.position ?? t("admin.jobs.detailTitle")}
      description={job ? `${job.company_name} · ${job.owner_email}` : undefined}
      onClose={onClose}
      footer={
        job && (
          <>
            <Button variant="danger-subtle" icon={<Trash2 size={15} />} onClick={() => onDelete(job)}>
              {t("admin.jobs.delete")}
            </Button>
            <Button variant="secondary" to={`/admin/applications?job_id=${job.id}`}>
              {t("admin.jobs.viewApplications")}
            </Button>
            <Button icon={<Pencil size={15} />} to={`/jobs/${job.id}`}>
              {t("admin.common.manage")}
            </Button>
          </>
        )
      }
    >
      {error ? (
        <EmptyState
          tone="error"
          title={t("errors.loadTitle")}
          message={getErrorMessage(error, t("errors.loadMessage"))}
          action={<Button onClick={reload}>{t("common.retry")}</Button>}
        />
      ) : loading || !job ? (
        <SkeletonText lines={6} />
      ) : (
        <div className="admin-detail">
          <dl className="detail-list">
            <dt>{t("admin.jobs.owner")}</dt>
            <dd>
              <Link to={`/admin/users/${job.owner_id}`}>{job.owner_name}</Link>
            </dd>
            <dt>{t("admin.jobs.created")}</dt>
            <dd>{formatDate(job.created_at)}</dd>
            <dt>{t("admin.jobs.requiredExperience")}</dt>
            <dd>{job.required_experience || "—"}</dd>
            <dt>{t("admin.jobs.requiredSkills")}</dt>
            <dd>{job.required_skills || "—"}</dd>
            <dt>{t("admin.jobs.publicForm")}</dt>
            <dd>{job.has_public_form ? t("common.yes") : t("common.no")}</dd>
            <dt>{t("admin.jobs.applications")}</dt>
            <dd>
              {job.applications_count} · {t("admin.jobs.candidatesCount", { count: job.candidates_count })} ·{" "}
              {t("admin.jobs.analyzedCount", { count: job.analyzed_count })}
            </dd>
          </dl>
          {job.status_breakdown.length > 0 && (
            <div className="admin-chip-row">
              {job.status_breakdown.map((item) => (
                <span key={item.key} className="admin-chip">
                  <ApplicationStatusBadge value={item.key} /> {item.count}
                </span>
              ))}
            </div>
          )}
          {job.description && <p className="detail-description">{job.description}</p>}
        </div>
      )}
    </Modal>
  );
}
