import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { ArrowLeft, Lock, MessagesSquare, RefreshCw } from "lucide-react";
import PageHeader from "../../components/ui/PageHeader";
import PageMeta from "../../components/seo/PageMeta";
import Badge from "../../components/ui/Badge";
import Button from "../../components/ui/Button";
import ConfirmDialog from "../../components/ui/ConfirmDialog";
import Spinner from "../../components/ui/Spinner";
import { SupportComposer, SupportThread } from "../../components/support/SupportThread";
import {
  SUPPORT_ADMIN_EVENT,
  requestAdminSupportUnreadRefresh,
} from "../../components/support/adminSupportBus";
import { useLatestRef } from "../../hooks/useLatestRef";
import { useLanguage } from "../../contexts/LanguageContext";
import { useToast } from "../../contexts/ToastContext";
import {
  closeSupportConversation,
  fetchAdminSupportConversation,
  fetchAdminSupportConversations,
  replyToSupportConversation,
} from "../../services/supportService";
import type { SupportAdminConversation, SupportAdminRow, SupportEvent } from "../../types/support";
import { ApiError } from "../../utils/apiError";
import { formatDateTime } from "../../utils/date";
import "../../styles/support.css";

type StatusFilter = "open" | "closed" | "";
type KindFilter = "hr" | "candidate" | "";

const PAGE_SIZE = 25;
/** Safety net next to the live stream (e.g. while it reconnects). */
const POLL_MS = 30_000;

function shortTime(iso: string): string {
  const date = new Date(iso);
  return date.toDateString() === new Date().toDateString()
    ? date.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" })
    : date.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

/**
 * Admin Support inbox: every Help Center conversation from HR users and
 * candidates, with live updates. Admins reply here and close a conversation
 * when the problem is solved; a closed conversation is read-only.
 */
export default function AdminSupportPage() {
  const { t } = useLanguage();
  const { notify } = useToast();
  const navigate = useNavigate();
  const params = useParams();
  const selectedId = params.id ? Number(params.id) : null;

  const [status, setStatus] = useState<StatusFilter>("open");
  const [kind, setKind] = useState<KindFilter>("");
  const [search, setSearch] = useState("");
  const [query, setQuery] = useState("");
  const [rows, setRows] = useState<SupportAdminRow[]>([]);
  const [total, setTotal] = useState(0);
  const [pages, setPages] = useState(1);
  const [listLoading, setListLoading] = useState(true);
  const [listError, setListError] = useState(false);

  const [detail, setDetail] = useState<SupportAdminConversation | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailMissing, setDetailMissing] = useState(false);
  const [confirmClose, setConfirmClose] = useState(false);
  const [closing, setClosing] = useState(false);

  const listRequest = useRef(0);
  const selectedRef = useLatestRef(selectedId);

  // Debounce the search box.
  useEffect(() => {
    const timer = window.setTimeout(() => setQuery(search.trim()), 300);
    return () => window.clearTimeout(timer);
  }, [search]);

  const loadList = useCallback(
    async (pageCount: number) => {
      const request = ++listRequest.current;
      try {
        const res = await fetchAdminSupportConversations({
          status: status || undefined,
          kind: kind || undefined,
          q: query || undefined,
          page: 1,
          limit: PAGE_SIZE * pageCount,
        });
        if (request !== listRequest.current) return;
        setRows(res.items);
        setTotal(res.total);
        setListError(false);
      } catch {
        if (request === listRequest.current) setListError(true);
      } finally {
        if (request === listRequest.current) setListLoading(false);
      }
    },
    [status, kind, query],
  );

  // Filters changed: back to the first page.
  useEffect(() => {
    setListLoading(true);
    setPages(1);
    void loadList(1);
  }, [loadList]);

  const loadDetail = useCallback(async (id: number, quiet = false) => {
    if (!quiet) setDetailLoading(true);
    try {
      const conversation = await fetchAdminSupportConversation(id);
      if (selectedRef.current !== id) return;
      setDetail(conversation);
      setDetailMissing(false);
      // Opening it marked it read: update the unread dot and the nav badge.
      setRows((current) => current.map((row) => (row.id === id ? { ...row, unread_count: 0 } : row)));
      requestAdminSupportUnreadRefresh();
    } catch (error) {
      if (selectedRef.current !== id) return;
      if (error instanceof ApiError && error.status === 404) setDetailMissing(true);
    } finally {
      if (!quiet) setDetailLoading(false);
    }
  }, [selectedRef]);

  useEffect(() => {
    setDetail(null);
    setDetailMissing(false);
    if (selectedId !== null && Number.isFinite(selectedId)) void loadDetail(selectedId);
  }, [selectedId, loadDetail]);

  // Live updates (forwarded by AdminSupportLive) and a slow safety-net poll.
  const pagesRef = useLatestRef(pages);
  useEffect(() => {
    function handle(raw: Event) {
      const event = (raw as CustomEvent<SupportEvent>).detail;
      void loadList(pagesRef.current);
      if (event.type !== "read" && event.conversation_id === selectedRef.current) {
        void loadDetail(event.conversation_id, true);
      }
    }
    window.addEventListener(SUPPORT_ADMIN_EVENT, handle);
    const timer = window.setInterval(() => {
      if (document.visibilityState !== "visible") return;
      void loadList(pagesRef.current);
      if (selectedRef.current !== null) void loadDetail(selectedRef.current, true);
    }, POLL_MS);
    return () => {
      window.removeEventListener(SUPPORT_ADMIN_EVENT, handle);
      window.clearInterval(timer);
    };
  }, [loadList, loadDetail, pagesRef, selectedRef]);

  async function reply(body: string) {
    if (!detail) return;
    try {
      const updated = await replyToSupportConversation(detail.id, body);
      setDetail(updated);
      void loadList(pagesRef.current);
    } catch (error) {
      notify({
        tone: "error",
        title:
          error instanceof ApiError && error.status === 409
            ? t("support.errors.closed")
            : t("support.errors.generic"),
      });
      throw error;
    }
  }

  async function closeConversation() {
    if (!detail) return;
    setClosing(true);
    try {
      setDetail(await closeSupportConversation(detail.id));
      setConfirmClose(false);
      notify({ tone: "success", title: t("support.admin.closedToast") });
      void loadList(pagesRef.current);
    } catch {
      notify({ tone: "error", title: t("support.errors.generic") });
    } finally {
      setClosing(false);
    }
  }

  const statusTabs: { value: StatusFilter; label: string }[] = [
    { value: "open", label: t("support.admin.filterOpen") },
    { value: "closed", label: t("support.admin.filterClosed") },
    { value: "", label: t("support.admin.filterAll") },
  ];
  const kindTabs: { value: KindFilter; label: string }[] = [
    { value: "", label: t("support.admin.kindAll") },
    { value: "hr", label: t("support.admin.kindHr") },
    { value: "candidate", label: t("support.admin.kindCandidate") },
  ];

  const kindLabel = (value: string) =>
    value === "candidate" ? t("support.admin.kindCandidate") : t("support.admin.kindHr");

  return (
    <>
      <PageMeta title={t("support.admin.title")} description={t("support.admin.description")} />
      <PageHeader
        title={t("support.admin.title")}
        description={t("support.admin.description")}
        action={
          <Button
            variant="secondary"
            size="sm"
            icon={<RefreshCw size={14} />}
            onClick={() => {
              void loadList(pages);
              if (selectedId !== null) void loadDetail(selectedId, true);
            }}
          >
            {t("support.admin.refresh")}
          </Button>
        }
      />

      <div className={`support-inbox${selectedId !== null ? " support-inbox--detail" : ""}`}>
        <aside className="support-inbox-list" aria-label={t("support.admin.listLabel")}>
          <div className="support-inbox-filters">
            <input
              type="search"
              className="support-inbox-search"
              placeholder={t("support.admin.searchPlaceholder")}
              aria-label={t("support.admin.searchPlaceholder")}
              value={search}
              onChange={(event) => setSearch(event.target.value)}
            />
            <div className="support-inbox-tabs" role="group" aria-label={t("support.admin.statusLabel")}>
              {statusTabs.map((tab) => (
                <button
                  key={tab.value || "all"}
                  type="button"
                  className="support-inbox-tab"
                  aria-pressed={status === tab.value}
                  onClick={() => setStatus(tab.value)}
                >
                  {tab.label}
                </button>
              ))}
            </div>
            <div className="support-inbox-tabs" role="group" aria-label={t("support.admin.kindLabel")}>
              {kindTabs.map((tab) => (
                <button
                  key={tab.value || "all"}
                  type="button"
                  className="support-inbox-tab"
                  aria-pressed={kind === tab.value}
                  onClick={() => setKind(tab.value)}
                >
                  {tab.label}
                </button>
              ))}
            </div>
          </div>

          {listLoading && rows.length === 0 ? (
            <div className="support-inbox-empty">
              <Spinner />
            </div>
          ) : listError && rows.length === 0 ? (
            <div className="support-inbox-empty">
              <p>{t("support.errors.load")}</p>
              <Button variant="secondary" size="sm" onClick={() => void loadList(pages)}>
                {t("support.retry")}
              </Button>
            </div>
          ) : rows.length === 0 ? (
            <div className="support-inbox-empty">{t("support.admin.empty")}</div>
          ) : (
            <ul className="support-inbox-items">
              {rows.map((row) => (
                <li key={row.id}>
                  <button
                    type="button"
                    className={`support-inbox-item${row.unread_count > 0 ? " support-inbox-item--unread" : ""}`}
                    aria-current={row.id === selectedId}
                    onClick={() => navigate(`/admin/support/${row.id}`)}
                  >
                    <div className="support-inbox-item-top">
                      <span className="support-inbox-item-name">{row.requester_name}</span>
                      <span className="support-inbox-item-time">{shortTime(row.last_message_at)}</span>
                    </div>
                    <p className="support-inbox-item-preview">{row.preview}</p>
                    <div className="support-inbox-item-tags">
                      <Badge tone={row.requester_kind === "candidate" ? "info" : "neutral"}>
                        {kindLabel(row.requester_kind)}
                      </Badge>
                      {row.status === "closed" && <Badge tone="neutral">{t("support.admin.closed")}</Badge>}
                      {row.unread_count > 0 && (
                        <Badge tone="primary">
                          {t("support.admin.unread").replace("{count}", String(row.unread_count))}
                        </Badge>
                      )}
                    </div>
                  </button>
                </li>
              ))}
              {rows.length < total && (
                <li className="support-inbox-more">
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => {
                      const next = pages + 1;
                      setPages(next);
                      void loadList(next);
                    }}
                  >
                    {t("support.admin.loadMore")}
                  </Button>
                </li>
              )}
            </ul>
          )}
        </aside>

        <section className="support-inbox-detail" aria-label={t("support.admin.detailLabel")}>
          {selectedId === null ? (
            <div className="help-panel-state">
              <MessagesSquare size={28} aria-hidden="true" />
              <p>{t("support.admin.pick")}</p>
            </div>
          ) : detailMissing ? (
            <div className="help-panel-state">
              <p>{t("support.admin.notFound")}</p>
            </div>
          ) : detailLoading || !detail ? (
            <div className="help-panel-state">
              <Spinner />
            </div>
          ) : (
            <>
              <header className="support-inbox-detail-header">
                <Button
                  variant="ghost"
                  size="sm"
                  className="support-inbox-back"
                  icon={<ArrowLeft size={16} />}
                  onClick={() => navigate("/admin/support")}
                  ariaLabel={t("support.admin.back")}
                  iconOnly
                />
                <div className="support-inbox-detail-who">
                  <h2>{detail.requester_name}</h2>
                  <div className="support-inbox-detail-meta">
                    <Badge tone={detail.requester_kind === "candidate" ? "info" : "neutral"}>
                      {kindLabel(detail.requester_kind)}
                    </Badge>
                    <span>{detail.requester_email}</span>
                    <span>
                      {t("support.admin.opened")} {formatDateTime(detail.created_at)}
                    </span>
                    {detail.page_url && (
                      <span>
                        {t("support.admin.page")} <code>{detail.page_url}</code>
                      </span>
                    )}
                  </div>
                </div>
                {detail.status === "open" && (
                  <Button variant="secondary" size="sm" icon={<Lock size={14} />} onClick={() => setConfirmClose(true)}>
                    {t("support.admin.close")}
                  </Button>
                )}
              </header>

              <SupportThread messages={detail.messages} viewer="admin" requesterLabel={detail.requester_name} />

              {detail.status === "open" ? (
                <SupportComposer key={detail.id} onSend={reply} placeholder={t("support.admin.replyPlaceholder")} />
              ) : (
                <div className="support-inbox-closed">
                  <Lock size={14} aria-hidden="true" />
                  {t("support.admin.closedBy")
                    .replace("{name}", detail.closed_by_name ?? t("support.team"))
                    .replace("{date}", detail.closed_at ? formatDateTime(detail.closed_at) : "")}
                </div>
              )}
            </>
          )}
        </section>
      </div>

      <ConfirmDialog
        open={confirmClose}
        title={t("support.admin.closeTitle")}
        message={t("support.admin.closeMessage")}
        confirmLabel={t("support.admin.close")}
        cancelLabel={t("support.admin.cancel")}
        loading={closing}
        onConfirm={() => void closeConversation()}
        onCancel={() => setConfirmClose(false)}
      />
    </>
  );
}
