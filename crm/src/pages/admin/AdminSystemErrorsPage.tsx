import { useCallback, useMemo } from "react";
import { Link } from "react-router-dom";
import PageHeader from "../../components/ui/PageHeader";
import PageMeta from "../../components/seo/PageMeta";
import Badge from "../../components/ui/Badge";
import Card from "../../components/ui/Card";
import FilterBar from "../../components/ui/FilterBar";
import StatCard from "../../components/ui/StatCard";
import { SkeletonCards } from "../../components/ui/Skeleton";
import ServerTable from "../../components/admin/ServerTable";
import { DateRangeFields, ToolbarSelect, useSearchInput } from "../../components/admin/filters";
import type { TableColumn } from "../../components/ui/Table";
import { useLanguage } from "../../contexts/LanguageContext";
import { useApiQuery } from "../../hooks/useApiQuery";
import { useUrlFilters } from "../../hooks/useUrlFilters";
import { fetchSystemErrors } from "../../services/adminService";
import { formatDateTime } from "../../utils/date";
import type { SystemErrorRow } from "../../types/admin";

const DEFAULTS = { q: "", status_code: "", date_from: "", date_to: "" };
const PAGE_SIZE = 50;
const STATUS_CODES = ["500", "502", "503", "504"];

export default function AdminSystemErrorsPage() {
  const { t } = useLanguage();
  const { values, page, setFilters, setPage, clear, active } = useUrlFilters(DEFAULTS);
  const commitSearch = useCallback((q: string) => setFilters({ q }), [setFilters]);
  const [search, setSearch] = useSearchInput(values.q, commitSearch);
  const params = { ...values, page, limit: PAGE_SIZE };
  const query = useApiQuery(() => fetchSystemErrors(params), JSON.stringify(params));
  const summary = query.data?.summary;

  const columns = useMemo<TableColumn<SystemErrorRow>[]>(
    () => [
      {
        header: t("admin.errors.time"),
        render: (row) => <span className="table-muted admin-nowrap">{formatDateTime(row.created_at)}</span>,
      },
      {
        header: t("admin.errors.status"),
        render: (row) => (
          <Badge tone={row.status_code === 503 ? "warning" : "danger"}>{row.status_code}</Badge>
        ),
      },
      {
        header: t("admin.errors.endpoint"),
        render: (row) => (
          <div>
            <code className="table-primary">
              {row.method} {row.path}
            </code>
            <div className="table-secondary">{row.error_type}</div>
          </div>
        ),
      },
      {
        header: t("admin.errors.message"),
        render: (row) => (
          <span className="table-muted admin-truncate" title={row.message}>
            {row.message || "—"}
          </span>
        ),
      },
      {
        header: t("admin.errors.user"),
        hideOnMobile: true,
        render: (row) =>
          row.user_id ? (
            <Link to={`/admin/users/${row.user_id}`}>{row.user_email ?? `#${row.user_id}`}</Link>
          ) : (
            <span className="table-muted">—</span>
          ),
      },
      {
        header: t("admin.errors.requestId"),
        hideOnMobile: true,
        render: (row) => <code className="table-secondary">{row.request_id ?? "—"}</code>,
      },
    ],
    [t],
  );

  return (
    <div className="page">
      <PageMeta title={t("admin.nav.systemErrors")} noindex />
      <PageHeader title={t("admin.errors.title")} description={t("admin.errors.description")} />

      {!summary ? (
        <SkeletonCards count={3} />
      ) : (
        <div className="stat-grid">
          <StatCard
            label={t("admin.errors.last24h")}
            value={summary.last_24h}
            tone={summary.last_24h > 0 ? "danger" : "success"}
          />
          <StatCard label={t("admin.errors.last7d")} value={summary.last_7d} />
          <StatCard
            label={t("admin.errors.byStatus")}
            value={
              summary.by_status_7d.length === 0
                ? "—"
                : summary.by_status_7d.map((item) => `${item.key}: ${item.count}`).join(" · ")
            }
            hint={t("admin.errors.last7dHint")}
          />
        </div>
      )}

      <p className="admin-note">{t("admin.errors.privacyNote")}</p>

      <Card flush>
        <FilterBar
          search={{ value: search, onChange: setSearch, placeholder: t("admin.errors.searchPlaceholder") }}
          active={active}
          onClear={clear}
        >
          <ToolbarSelect
            label={t("admin.errors.status")}
            value={values.status_code}
            onChange={(status_code) => setFilters({ status_code })}
            allLabel={t("labels.all")}
            options={STATUS_CODES.map((code) => ({ value: code, label: code }))}
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
          caption={t("admin.errors.title")}
          onPageChange={setPage}
          filtered={active}
          onClearFilters={clear}
          emptyTitle={t("admin.errors.emptyTitle")}
          emptyMessage={t("admin.errors.emptyMessage")}
        />
      </Card>
    </div>
  );
}
