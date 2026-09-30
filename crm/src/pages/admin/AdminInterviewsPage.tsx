import { useCallback, useMemo } from "react";
import { Link } from "react-router-dom";
import { Pencil } from "lucide-react";
import PageHeader from "../../components/ui/PageHeader";
import PageMeta from "../../components/seo/PageMeta";
import Card from "../../components/ui/Card";
import FilterBar from "../../components/ui/FilterBar";
import InterviewStatusBadge from "../../components/ui/InterviewStatusBadge";
import StatCard from "../../components/ui/StatCard";
import { SkeletonCards } from "../../components/ui/Skeleton";
import ServerTable from "../../components/admin/ServerTable";
import {
  CompanySelect,
  DateRangeFields,
  OwnerSelect,
  ToolbarSelect,
  nextSort,
  useSearchInput,
} from "../../components/admin/filters";
import type { TableColumn } from "../../components/ui/Table";
import { useLanguage } from "../../contexts/LanguageContext";
import { useApiQuery } from "../../hooks/useApiQuery";
import { useUrlFilters } from "../../hooks/useUrlFilters";
import { fetchAdminInterviews } from "../../services/adminService";
import { formatDate, formatDateTime } from "../../utils/date";
import { translateOr } from "../../utils/statusLabels";
import type { AdminInterviewRow } from "../../types/admin";

const DEFAULTS = {
  q: "",
  owner_id: "",
  company: "",
  status: "",
  date_from: "",
  date_to: "",
  sort: "scheduled_at",
  order: "desc",
};
const PAGE_SIZE = 25;
const STATUSES = ["upcoming", "completed", "cancelled"];

export default function AdminInterviewsPage() {
  const { t } = useLanguage();
  const { values, page, setFilters, setPage, clear, active } = useUrlFilters(DEFAULTS);
  const commitSearch = useCallback((q: string) => setFilters({ q }), [setFilters]);
  const [search, setSearch] = useSearchInput(values.q, commitSearch);
  const params = { ...values, page, limit: PAGE_SIZE };
  const query = useApiQuery(() => fetchAdminInterviews(params), JSON.stringify(params));
  const summary = query.data?.summary;

  const columns = useMemo<TableColumn<AdminInterviewRow>[]>(
    () => [
      {
        header: t("admin.interviews.candidate"),
        render: (row) => (
          <div>
            <Link className="table-primary" to={`/admin/candidates/${row.candidate_id}`}>
              {row.candidate_name}
            </Link>
            <div className="table-secondary">{row.interviewer}</div>
          </div>
        ),
      },
      {
        header: t("admin.interviews.job"),
        render: (row) => (
          <div>
            <Link className="table-primary" to={`/admin/jobs?job=${row.job_id}`}>
              {row.position}
            </Link>
            <div className="table-secondary">{row.company_name}</div>
          </div>
        ),
      },
      {
        header: t("admin.interviews.hr"),
        hideOnMobile: true,
        render: (row) => (
          <Link className="table-muted" to={`/admin/users/${row.hr_id}`}>
            {row.hr_email}
          </Link>
        ),
      },
      { header: t("admin.interviews.status"), render: (row) => <InterviewStatusBadge value={row.status} /> },
      {
        header: t("admin.interviews.scheduled"),
        sortKey: "scheduled_at",
        render: (row) => (
          <div>
            <div>{formatDateTime(row.scheduled_at)}</div>
            <div className="table-secondary">{t("common.minutes", { count: row.duration_minutes })}</div>
          </div>
        ),
      },
      {
        header: t("admin.interviews.created"),
        sortKey: "created_at",
        hideOnMobile: true,
        render: (row) => <span className="table-muted admin-nowrap">{formatDate(row.created_at)}</span>,
      },
      {
        header: t("labels.actions"),
        headerClassName: "table-actions-cell",
        className: "table-actions-cell",
        // Admins have every HR permission: reschedule, change the status or
        // edit notes on the regular interview screen.
        render: (row) => (
          <span className="row-actions">
            <Link
              className="row-action row-action--icon"
              title={t("admin.common.manage")}
              aria-label={`${t("admin.common.manage")}: ${row.candidate_name}`}
              to={`/interviews/${row.id}`}
            >
              <Pencil size={15} aria-hidden="true" />
            </Link>
          </span>
        ),
      },
    ],
    [t],
  );

  return (
    <div className="page">
      <PageMeta title={t("admin.nav.interviews")} noindex />
      <PageHeader title={t("admin.interviews.title")} description={t("admin.interviews.description")} />

      {!summary ? (
        <SkeletonCards count={4} />
      ) : (
        <>
          <div className="stat-grid">
            <StatCard label={t("admin.interviews.total")} value={summary.total} />
            <StatCard label={t("admin.interviews.upcoming")} value={summary.upcoming} tone="info" />
            <StatCard label={t("admin.interviews.completed")} value={summary.completed} tone="success" />
            <StatCard
              label={t("admin.interviews.overdue")}
              value={summary.overdue}
              hint={t("admin.interviews.overdueHint")}
              tone={summary.overdue > 0 ? "warning" : "default"}
            />
          </div>
          <div className="stat-grid">
            {(["in_process", "completed", "not_completed"] as const).map((status) => (
              <StatCard
                key={status}
                label={translateOr(t, `statusMeta.interview.${status}`, status)}
                value={summary.candidate_progress[status] ?? 0}
                hint={t("admin.interviews.candidateProgress")}
              />
            ))}
            <StatCard label={t("admin.interviews.cancelled")} value={summary.cancelled} />
          </div>
        </>
      )}

      <Card flush>
        <FilterBar
          search={{ value: search, onChange: setSearch, placeholder: t("admin.interviews.searchPlaceholder") }}
          active={active}
          onClear={clear}
        >
          <OwnerSelect value={values.owner_id} onChange={(owner_id) => setFilters({ owner_id })} />
          <CompanySelect value={values.company} onChange={(company) => setFilters({ company })} />
          <ToolbarSelect
            label={t("admin.interviews.status")}
            value={values.status}
            onChange={(status) => setFilters({ status })}
            allLabel={t("labels.all")}
            options={STATUSES.map((value) => ({
              value,
              label: translateOr(t, `statusMeta.interviewFilter.${value}`, value),
            }))}
          />
          <DateRangeFields from={values.date_from} to={values.date_to} onChange={setFilters} />
        </FilterBar>

        <ServerTable
          columns={columns}
          data={query.data}
          loading={query.loading}
          error={query.error}
          onRetry={query.reload}
          rowKey={(row) => row.id}
          caption={t("admin.interviews.title")}
          onPageChange={setPage}
          sort={{ key: values.sort, order: values.order as "asc" | "desc" }}
          onSortChange={(key) => setFilters(nextSort(values, key))}
          filtered={active}
          onClearFilters={clear}
          emptyTitle={t("admin.interviews.emptyTitle")}
          emptyMessage={t("admin.interviews.emptyMessage")}
        />
      </Card>
    </div>
  );
}
