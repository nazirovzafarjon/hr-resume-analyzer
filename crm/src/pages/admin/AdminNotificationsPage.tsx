import { useCallback, useMemo, useState } from "react";
import { Eye, Mail, MailCheck, MailOpen, RefreshCw, Trash2 } from "lucide-react";
import PageHeader from "../../components/ui/PageHeader";
import PageMeta from "../../components/seo/PageMeta";
import Card from "../../components/ui/Card";
import FilterBar from "../../components/ui/FilterBar";
import ServerTable from "../../components/admin/ServerTable";
import Badge from "../../components/ui/Badge";
import Button from "../../components/ui/Button";
import Modal from "../../components/ui/Modal";
import ConfirmDialog from "../../components/ui/ConfirmDialog";
import { ToolbarSelect, useSearchInput } from "../../components/admin/filters";
import type { TableColumn } from "../../components/ui/Table";
import { useLanguage } from "../../contexts/LanguageContext";
import { useToast } from "../../contexts/ToastContext";
import { useApiQuery } from "../../hooks/useApiQuery";
import { useUrlFilters } from "../../hooks/useUrlFilters";
import {
  deleteAdminNotification,
  fetchAdminNotifications,
  markAdminNotificationRead,
} from "../../services/adminService";
import { formatDateTime } from "../../utils/date";
import type { ContactNotificationRow } from "../../types/admin";

const DEFAULTS = { q: "", status: "" };
const PAGE_SIZE = 25;

export default function AdminNotificationsPage() {
  const { t } = useLanguage();
  const { notify } = useToast();
  const { values, page, setFilters, setPage, clear, active } = useUrlFilters(DEFAULTS);

  const commitSearch = useCallback((q: string) => setFilters({ q }), [setFilters]);
  const [search, setSearch] = useSearchInput(values.q, commitSearch);

  const [selectedMessage, setSelectedMessage] = useState<ContactNotificationRow | null>(null);
  const [pendingDelete, setPendingDelete] = useState<ContactNotificationRow | null>(null);
  const [deleteBusy, setDeleteBusy] = useState(false);

  const isReadParam =
    values.status === "unread" ? false : values.status === "read" ? true : undefined;

  const params = {
    q: values.q || undefined,
    is_read: isReadParam,
    page,
    limit: PAGE_SIZE,
  };

  const query = useApiQuery(
    () => fetchAdminNotifications(params),
    JSON.stringify({ ...values, page }),
  );

  const openMessage = useCallback(
    async (row: ContactNotificationRow) => {
      setSelectedMessage(row);
      if (!row.is_read) {
        try {
          const updated = await markAdminNotificationRead(row.id, true);
          setSelectedMessage(updated);
          query.reload();
        } catch {
          // Non-critical, ignore
        }
      }
    },
    [query],
  );

  const handleToggleRead = useCallback(
    async (row: ContactNotificationRow, e?: React.MouseEvent) => {
      e?.stopPropagation();
      try {
        const nextState = !row.is_read;
        const updated = await markAdminNotificationRead(row.id, nextState);
        if (selectedMessage?.id === row.id) {
          setSelectedMessage(updated);
        }
        query.reload();
        notify({
          tone: "info",
          title: nextState
            ? t("admin.notifications.markAsRead")
            : t("admin.notifications.markAsUnread"),
        });
      } catch (err) {
        notify({
          tone: "error",
          title: t("errors.unknownTitle"),
          message: err instanceof Error ? err.message : undefined,
        });
      }
    },
    [selectedMessage, query, notify, t],
  );

  const handleConfirmDelete = useCallback(async () => {
    if (!pendingDelete) return;
    setDeleteBusy(true);
    try {
      await deleteAdminNotification(pendingDelete.id);
      if (selectedMessage?.id === pendingDelete.id) {
        setSelectedMessage(null);
      }
      setPendingDelete(null);
      query.reload();
      notify({
        tone: "success",
        title: t("admin.notifications.deleteSuccess"),
      });
    } catch (err) {
      notify({
        tone: "error",
        title: t("errors.unknownTitle"),
        message: err instanceof Error ? err.message : undefined,
      });
    } finally {
      setDeleteBusy(false);
    }
  }, [pendingDelete, selectedMessage, query, notify, t]);

  const columns = useMemo<TableColumn<ContactNotificationRow>[]>(
    () => [
      {
        header: t("admin.notifications.status"),
        className: "table-actions-cell",
        render: (row) => (
          <Badge tone={row.is_read ? "neutral" : "warning"} dot>
            {row.is_read
              ? t("admin.notifications.isReadBadge")
              : t("admin.notifications.isUnreadBadge")}
          </Badge>
        ),
      },
      {
        header: t("admin.notifications.sender"),
        render: (row) => (
          <div
            className="cursor-pointer"
            onClick={() => void openMessage(row)}
            role="button"
            tabIndex={0}
            onKeyDown={(e) => {
              if (e.key === "Enter") void openMessage(row);
            }}
          >
            <div
              className="table-primary"
              style={{ fontWeight: row.is_read ? "normal" : "600" }}
            >
              {row.name}
            </div>
            <a
              className="table-secondary"
              href={`mailto:${row.email}`}
              onClick={(e) => e.stopPropagation()}
            >
              {row.email}
            </a>
          </div>
        ),
      },
      {
        header: t("admin.notifications.subject"),
        render: (row) => (
          <div
            className="cursor-pointer"
            onClick={() => void openMessage(row)}
            role="button"
            tabIndex={0}
            onKeyDown={(e) => {
              if (e.key === "Enter") void openMessage(row);
            }}
          >
            <div
              className="table-primary"
              style={{ fontWeight: row.is_read ? "normal" : "600" }}
            >
              {row.subject || t("admin.notifications.noSubject")}
            </div>
            <div
              className="table-muted admin-truncate"
              style={{ maxWidth: 380 }}
              title={row.message}
            >
              {row.message}
            </div>
          </div>
        ),
      },
      {
        header: t("admin.notifications.received"),
        hideOnMobile: true,
        render: (row) => (
          <span className="table-muted admin-nowrap">{formatDateTime(row.created_at)}</span>
        ),
      },
      {
        header: t("labels.actions"),
        headerClassName: "table-actions-cell",
        className: "table-actions-cell",
        render: (row) => (
          <div className="table-actions" onClick={(e) => e.stopPropagation()}>
            <Button
              variant="ghost"
              size="sm"
              icon={<Eye size={16} />}
              onClick={() => void openMessage(row)}
              aria-label={t("common.view")}
              title={t("common.view")}
            />
            <Button
              variant="ghost"
              size="sm"
              icon={row.is_read ? <Mail size={16} /> : <MailCheck size={16} />}
              onClick={(e) => void handleToggleRead(row, e)}
              aria-label={
                row.is_read
                  ? t("admin.notifications.markAsUnread")
                  : t("admin.notifications.markAsRead")
              }
              title={
                row.is_read
                  ? t("admin.notifications.markAsUnread")
                  : t("admin.notifications.markAsRead")
              }
            />
            <Button
              variant="ghost"
              size="sm"
              icon={<Trash2 size={16} />}
              onClick={(e) => {
                e.stopPropagation();
                setPendingDelete(row);
              }}
              aria-label={t("common.delete")}
              title={t("common.delete")}
            />
          </div>
        ),
      },
    ],
    [t, openMessage, handleToggleRead],
  );

  const statusOptions = useMemo(
    () => [
      { value: "unread", label: t("admin.notifications.statusUnread") },
      { value: "read", label: t("admin.notifications.statusRead") },
    ],
    [t],
  );

  const unreadCount = query.data?.unread_count ?? 0;
  const totalCount = query.data?.total ?? 0;

  return (
    <>
      <PageMeta
        title={`${t("admin.notifications.title")} · ${t("app.name")}`}
        description={t("admin.notifications.description")}
      />

      <PageHeader
        title={t("admin.notifications.title")}
        description={t("admin.notifications.description")}
        action={
          <div style={{ display: "flex", alignItems: "center", gap: "var(--space-sm)" }}>
            <span className="table-secondary">
              {totalCount} {t("admin.notifications.total").toLowerCase()}
            </span>
            {unreadCount > 0 && (
              <Badge tone="warning" dot>
                {unreadCount} {t("admin.notifications.unread").toLowerCase()}
              </Badge>
            )}
            <Button
              variant="secondary"
              size="sm"
              icon={<RefreshCw size={14} className={query.loading ? "spin" : undefined} />}
              onClick={query.reload}
              disabled={query.loading}
            >
              {t("admin.common.refresh")}
            </Button>
          </div>
        }
      />

      <Card>
        <FilterBar
          search={{
            value: search,
            onChange: setSearch,
            placeholder: t("admin.notifications.searchPlaceholder"),
          }}
          active={active}
          onClear={clear}
        >
          <ToolbarSelect
            label={t("admin.notifications.status")}
            value={values.status}
            allLabel={t("admin.notifications.statusAll")}
            options={statusOptions}
            onChange={(status) => setFilters({ status })}
          />
        </FilterBar>

        <ServerTable
          columns={columns}
          data={query.data}
          loading={query.loading}
          error={query.error}
          onRetry={query.reload}
          rowKey={(row) => row.id}
          caption={t("admin.notifications.title")}
          onPageChange={setPage}
          filtered={active}
          onClearFilters={clear}
          emptyTitle={t("admin.notifications.emptyTitle")}
          emptyMessage={t("admin.notifications.emptyMessage")}
        />
      </Card>

      {/* Message Details Modal */}
      {selectedMessage && (
        <Modal
          open={Boolean(selectedMessage)}
          title={selectedMessage.subject || t("admin.notifications.detailTitle")}
          description={formatDateTime(selectedMessage.created_at)}
          onClose={() => setSelectedMessage(null)}
          size="lg"
          footer={
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                width: "100%",
              }}
            >
              <Button
                variant="danger"
                size="sm"
                icon={<Trash2 size={16} />}
                onClick={() => {
                  setPendingDelete(selectedMessage);
                }}
              >
                {t("common.delete")}
              </Button>
              <div style={{ display: "flex", gap: "var(--space-sm)" }}>
                <Button
                  variant="secondary"
                  size="sm"
                  icon={selectedMessage.is_read ? <Mail size={16} /> : <MailCheck size={16} />}
                  onClick={() => void handleToggleRead(selectedMessage)}
                >
                  {selectedMessage.is_read
                    ? t("admin.notifications.markAsUnread")
                    : t("admin.notifications.markAsRead")}
                </Button>
                <a
                  className="btn btn--primary"
                  href={`mailto:${selectedMessage.email}?subject=Re: ${encodeURIComponent(
                    selectedMessage.subject || "Contact Inquiry",
                  )}`}
                >
                  <MailOpen size={16} />
                  <span>{t("admin.notifications.replyTo")}</span>
                </a>
              </div>
            </div>
          }
        >
          <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-md)" }}>
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
                gap: "var(--space-sm)",
                padding: "var(--space-md)",
                backgroundColor: "var(--color-surface-sunken)",
                borderRadius: "var(--radius-md)",
                border: "1px solid var(--color-border)",
              }}
            >
              <div>
                <p className="table-secondary" style={{ marginBottom: "2px" }}>
                  {t("admin.notifications.sender")}
                </p>
                <p style={{ fontWeight: 600 }}>{selectedMessage.name}</p>
              </div>
              <div>
                <p className="table-secondary" style={{ marginBottom: "2px" }}>
                  Email
                </p>
                <a href={`mailto:${selectedMessage.email}`} className="table-primary">
                  {selectedMessage.email}
                </a>
              </div>
              <div>
                <p className="table-secondary" style={{ marginBottom: "2px" }}>
                  {t("admin.notifications.received")}
                </p>
                <p className="table-muted">{formatDateTime(selectedMessage.created_at)}</p>
              </div>
              <div>
                <p className="table-secondary" style={{ marginBottom: "2px" }}>
                  {t("admin.notifications.status")}
                </p>
                <Badge tone={selectedMessage.is_read ? "neutral" : "warning"} dot>
                  {selectedMessage.is_read
                    ? t("admin.notifications.isReadBadge")
                    : t("admin.notifications.isUnreadBadge")}
                </Badge>
              </div>
            </div>

            <div>
              <p className="table-secondary" style={{ marginBottom: "var(--space-xs)" }}>
                {t("admin.notifications.subject")}
              </p>
              <div
                style={{
                  padding: "var(--space-md)",
                  backgroundColor: "var(--color-surface)",
                  borderRadius: "var(--radius-md)",
                  border: "1px solid var(--color-border)",
                  whiteSpace: "pre-wrap",
                  fontFamily: "inherit",
                  fontSize: "var(--text-sm)",
                  lineHeight: 1.6,
                  maxHeight: "360px",
                  overflowY: "auto",
                }}
              >
                {selectedMessage.message}
              </div>
            </div>
          </div>
        </Modal>
      )}

      {/* Delete Confirmation Dialog */}
      <ConfirmDialog
        open={Boolean(pendingDelete)}
        title={t("admin.notifications.deleteTitle")}
        message={t("admin.notifications.deleteMessage").replace(
          "{name}",
          pendingDelete?.name || "",
        )}
        confirmLabel={t("common.delete")}
        cancelLabel={t("common.cancel")}
        danger
        loading={deleteBusy}
        onConfirm={() => void handleConfirmDelete()}
        onCancel={() => setPendingDelete(null)}
      />
    </>
  );
}
