import { useCallback, useMemo } from "react";
import { Link } from "react-router-dom";
import { X } from "lucide-react";
import PageHeader from "../../components/ui/PageHeader";
import PageMeta from "../../components/seo/PageMeta";
import Card from "../../components/ui/Card";
import FilterBar from "../../components/ui/FilterBar";
import ServerTable from "../../components/admin/ServerTable";
import { auditResourceLink, useAuditActionLabel } from "../../components/admin/AuditActivityList";
import { DateRangeFields, ToolbarSelect, useSearchInput } from "../../components/admin/filters";
import type { TableColumn } from "../../components/ui/Table";
import { useLanguage } from "../../contexts/LanguageContext";
import { useApiQuery } from "../../hooks/useApiQuery";
import { useUrlFilters } from "../../hooks/useUrlFilters";
import { fetchAuditLogs, fetchAuditMeta } from "../../services/adminService";
import { formatDateTime } from "../../utils/date";
import type { AuditLogEntry } from "../../types/admin";

const DEFAULTS = { q: "", action: "", resource_type: "", actor_id: "", date_from: "", date_to: "" };
const PAGE_SIZE = 50;

/** Compact "key: value" rendering of the (already sanitized) details. */
function formatDetails(details: AuditLogEntry["details"]): string {
  if (!details) return "";
  return Object.entries(details)
    .map(([key, value]) => `${key}: ${Array.isArray(value) ? value.join(", ") : String(value)}`)
    .join(" · ");
}

export default function AdminAuditLogsPage() {
  const { t } = useLanguage();
  const actionLabel = useAuditActionLabel();
  const { values, page, setFilters, setPage, clear, active } = useUrlFilters(DEFAULTS);
  const commitSearch = useCallback((q: string) => setFilters({ q }), [setFilters]);
  const [search, setSearch] = useSearchInput(values.q, commitSearch);
  const meta = useApiQuery(fetchAuditMeta, "audit-meta");
  const params = { ...values, page, limit: PAGE_SIZE };
  const query = useApiQuery(() => fetchAuditLogs(params), JSON.stringify(params));

  const columns = useMemo<TableColumn<AuditLogEntry>[]>(
    () => [
      {
        header: t("admin.audit.time"),
        render: (row) => <span className="table-muted admin-nowrap">{formatDateTime(row.created_at)}</span>,
      },
      {
        header: t("admin.audit.actor"),
        render: (row) =>
          row.actor_user_id ? (
            <Link to={`/admin/users/${row.actor_user_id}`}>{row.actor_email}</Link>
          ) : (
            <span className="table-muted">{row.actor_email ?? t("admin.audit.system")}</span>
          ),
      },
      {
        header: t("admin.audit.action"),
        render: (row) => (
          <div>
            <div className="table-primary">{actionLabel(row.action)}</div>
            <code className="table-secondary">{row.action}</code>
          </div>
        ),
      },
      {
        header: t("admin.audit.resource"),
        render: (row) => {
          const label = row.resource_id ? `${row.resource_type} #${row.resource_id}` : row.resource_type;
          const link = auditResourceLink(row);
          return link ? <Link to={link}>{label}</Link> : <span>{label}</span>;
        },
      },
      {
        header: t("admin.audit.details"),
        hideOnMobile: true,
        render: (row) => {
          const text = formatDetails(row.details);
          return (
            <span className="table-muted admin-truncate" title={text}>
              {text || "—"}
            </span>
          );
        },
      },
      {
        header: t("admin.audit.requestId"),
        hideOnMobile: true,
        render: (row) => <code className="table-secondary">{row.request_id ?? "—"}</code>,
      },
      {
        header: t("admin.audit.ip"),
        hideOnMobile: true,
        render: (row) => (
          <span className="table-muted" title={row.user_agent ?? undefined}>
            {row.ip_address ?? "—"}
          </span>
        ),
      },
    ],
    [t, actionLabel],
  );

  return (
    <div className="page">
      <PageMeta title={t("admin.nav.auditLogs")} noindex />
      <PageHeader title={t("admin.audit.title")} description={t("admin.audit.description")} />

      <Card flush>
        <FilterBar
          search={{ value: search, onChange: setSearch, placeholder: t("admin.audit.searchPlaceholder") }}
          active={active}
          onClear={clear}
        >
          <ToolbarSelect
            label={t("admin.audit.action")}
            value={values.action}
            onChange={(action) => setFilters({ action })}
            allLabel={t("labels.all")}
            options={(meta.data?.actions ?? []).map((value) => ({ value, label: actionLabel(value) }))}
          />
          <ToolbarSelect
            label={t("admin.audit.resource")}
            value={values.resource_type}
            onChange={(resource_type) => setFilters({ resource_type })}
            allLabel={t("labels.all")}
            options={(meta.data?.resource_types ?? []).map((value) => ({
              value,
              label: t(`admin.audit.resources.${value}`),
            }))}
          />
          <DateRangeFields from={values.date_from} to={values.date_to} onChange={setFilters} />
        </FilterBar>

        {values.actor_id && (
          <div className="admin-filter-chip-row">
            <span className="admin-chip">
              {t("admin.audit.actorFilter", { id: values.actor_id })}
              <button
                type="button"
                className="admin-chip-remove"
                onClick={() => setFilters({ actor_id: "" })}
                aria-label={t("common.clearFilters")}
              >
                <X size={12} aria-hidden="true" />
              </button>
            </span>
          </div>
        )}

        <ServerTable
          columns={columns}
          data={query.data}
          loading={query.loading}
          error={query.error}
          onRetry={query.reload}
          rowKey={(row) => row.id}
          caption={t("admin.audit.title")}
          onPageChange={setPage}
          filtered={active}
          onClearFilters={clear}
          emptyTitle={t("admin.audit.emptyTitle")}
          emptyMessage={t("admin.audit.emptyMessage")}
        />
      </Card>
    </div>
  );
}
