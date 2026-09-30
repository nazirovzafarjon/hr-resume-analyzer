import { useCallback, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Eye, Pencil, ShieldOff, ShieldPlus, Trash2, UserCheck, UserX } from "lucide-react";
import PageHeader from "../../components/ui/PageHeader";
import PageMeta from "../../components/seo/PageMeta";
import Card from "../../components/ui/Card";
import FilterBar from "../../components/ui/FilterBar";
import ServerTable from "../../components/admin/ServerTable";
import EditUserDialog from "../../components/admin/EditUserDialog";
import UserActionDialog, { type UserAction } from "../../components/admin/UserActionDialog";
import { AccountStatusBadge, RoleBadge } from "../../components/admin/badges";
import {
  DateRangeFields,
  ToolbarSelect,
  nextSort,
  useSearchInput,
} from "../../components/admin/filters";
import type { TableColumn } from "../../components/ui/Table";
import { useLanguage } from "../../contexts/LanguageContext";
import { useApiQuery } from "../../hooks/useApiQuery";
import { useCurrentUser } from "../../hooks/useCurrentUser";
import { useUrlFilters } from "../../hooks/useUrlFilters";
import { fetchAdminUsers } from "../../services/adminService";
import { formatDate, formatDateTime } from "../../utils/date";
import type { AdminUserRow } from "../../types/admin";

const DEFAULTS = {
  q: "",
  status: "",
  role: "",
  date_from: "",
  date_to: "",
  sort: "created_at",
  order: "desc",
};

const PAGE_SIZE = 25;

export default function AdminUsersPage() {
  const { t } = useLanguage();
  const { user: me } = useCurrentUser();
  const { values, page, setFilters, setPage, clear, active } = useUrlFilters(DEFAULTS);
  const commitSearch = useCallback((q: string) => setFilters({ q }), [setFilters]);
  const [search, setSearch] = useSearchInput(values.q, commitSearch);
  const [pending, setPending] = useState<{ action: UserAction; user: AdminUserRow } | null>(null);
  const [editing, setEditing] = useState<AdminUserRow | null>(null);

  const params = { ...values, page, limit: PAGE_SIZE };
  const query = useApiQuery(() => fetchAdminUsers(params), JSON.stringify(params));

  const columns = useMemo<TableColumn<AdminUserRow>[]>(() => {
    const isSelf = (row: AdminUserRow) => row.id === me?.id;
    return [
      {
        header: t("admin.users.name"),
        sortKey: "name",
        render: (row) => (
          <div>
            <Link className="table-primary" to={`/admin/users/${row.id}`}>
              {row.full_name}
            </Link>
            <div className="table-secondary">{row.email}</div>
          </div>
        ),
      },
      { header: t("admin.users.role"), render: (row) => <RoleBadge admin={row.is_superuser} /> },
      { header: t("admin.users.status"), render: (row) => <AccountStatusBadge active={row.is_active} /> },
      {
        header: t("admin.users.jobs"),
        sortKey: "jobs",
        className: "table-number",
        render: (row) => row.jobs_count,
      },
      {
        header: t("admin.users.applications"),
        sortKey: "applications",
        className: "table-number",
        render: (row) => row.applications_count,
      },
      {
        header: t("admin.users.joined"),
        sortKey: "created_at",
        hideOnMobile: true,
        render: (row) => <span className="table-muted admin-nowrap">{formatDate(row.created_at)}</span>,
      },
      {
        header: t("admin.users.lastActivity"),
        sortKey: "last_login_at",
        hideOnMobile: true,
        render: (row) => (
          <span className="table-muted admin-nowrap">
            {row.last_login_at ? formatDateTime(row.last_login_at) : t("admin.users.never")}
          </span>
        ),
      },
      {
        header: t("labels.actions"),
        headerClassName: "table-actions-cell",
        className: "table-actions-cell",
        render: (row) => (
          <span className="row-actions">
            <Link
              className="row-action row-action--icon"
              to={`/admin/users/${row.id}`}
              title={t("admin.common.view")}
              aria-label={`${t("admin.common.view")}: ${row.full_name}`}
            >
              <Eye size={15} aria-hidden="true" />
            </Link>
            <button
              type="button"
              className="row-action row-action--icon"
              title={t("admin.users.edit.action")}
              aria-label={`${t("admin.users.edit.action")}: ${row.full_name}`}
              onClick={() => setEditing(row)}
            >
              <Pencil size={15} aria-hidden="true" />
            </button>
            {/* Self-protection mirrors the backend: no self-demotion,
                deactivation or deletion is even offered. */}
            {!isSelf(row) && (
              <>
                <button
                  type="button"
                  className="row-action row-action--icon"
                  title={row.is_active ? t("admin.users.deactivate") : t("admin.users.activate")}
                  aria-label={`${row.is_active ? t("admin.users.deactivate") : t("admin.users.activate")}: ${row.full_name}`}
                  onClick={() => setPending({ action: row.is_active ? "deactivate" : "activate", user: row })}
                >
                  {row.is_active ? <UserX size={15} aria-hidden="true" /> : <UserCheck size={15} aria-hidden="true" />}
                </button>
                <button
                  type="button"
                  className="row-action row-action--icon"
                  title={row.is_superuser ? t("admin.users.demote") : t("admin.users.promote")}
                  aria-label={`${row.is_superuser ? t("admin.users.demote") : t("admin.users.promote")}: ${row.full_name}`}
                  onClick={() => setPending({ action: row.is_superuser ? "demote" : "promote", user: row })}
                >
                  {row.is_superuser ? <ShieldOff size={15} aria-hidden="true" /> : <ShieldPlus size={15} aria-hidden="true" />}
                </button>
                <button
                  type="button"
                  className="row-action row-action--icon row-action--danger"
                  title={t("admin.users.delete")}
                  aria-label={`${t("admin.users.delete")}: ${row.full_name}`}
                  onClick={() => setPending({ action: "delete", user: row })}
                >
                  <Trash2 size={15} aria-hidden="true" />
                </button>
              </>
            )}
          </span>
        ),
      },
    ];
  }, [t, me?.id]);

  return (
    <div className="page">
      <PageMeta title={t("admin.nav.users")} noindex />
      <PageHeader title={t("admin.users.title")} description={t("admin.users.description")} />

      <Card flush>
        <FilterBar
          search={{ value: search, onChange: setSearch, placeholder: t("admin.users.searchPlaceholder") }}
          active={active}
          onClear={clear}
        >
          <ToolbarSelect
            label={t("admin.users.status")}
            value={values.status}
            onChange={(status) => setFilters({ status })}
            allLabel={t("labels.all")}
            options={[
              { value: "active", label: t("admin.users.active") },
              { value: "inactive", label: t("admin.users.inactive") },
            ]}
          />
          <ToolbarSelect
            label={t("admin.users.role")}
            value={values.role}
            onChange={(role) => setFilters({ role })}
            allLabel={t("labels.all")}
            options={[
              { value: "admin", label: t("admin.users.roleAdmin") },
              { value: "hr", label: t("admin.users.roleHr") },
            ]}
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
          caption={t("admin.users.title")}
          onPageChange={setPage}
          sort={{ key: values.sort, order: values.order as "asc" | "desc" }}
          onSortChange={(key) => setFilters(nextSort(values, key))}
          filtered={active}
          onClearFilters={clear}
          emptyTitle={t("admin.users.emptyTitle")}
          emptyMessage={t("admin.users.emptyMessage")}
        />
      </Card>

      <EditUserDialog
        user={editing}
        isSelf={editing?.id === me?.id}
        onClose={() => setEditing(null)}
        onDone={() => {
          setEditing(null);
          query.reload();
        }}
      />

      <UserActionDialog
        pending={pending}
        onClose={() => setPending(null)}
        onDone={() => {
          setPending(null);
          query.reload();
        }}
      />
    </div>
  );
}
