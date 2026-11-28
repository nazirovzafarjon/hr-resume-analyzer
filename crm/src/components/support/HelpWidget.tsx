import { useCallback, useEffect, useRef, useState } from "react";
import { useLocation } from "react-router-dom";
import { LifeBuoy, Lock, MessageSquarePlus, X } from "lucide-react";
import { useLanguage } from "../../contexts/LanguageContext";
import { useToast } from "../../contexts/ToastContext";
import { useSupportStream } from "../../hooks/useSupportStream";
import type { SessionKind } from "../../services/apiClient";
import {
  fetchMySupportConversation,
  fetchMySupportConversations,
  fetchMySupportUnreadCount,
  openSupportConversation,
  sendSupportMessage,
  supportBase,
} from "../../services/supportService";
import type { SupportConversation, SupportEvent } from "../../types/support";
import { ApiError } from "../../utils/apiError";
import Spinner from "../ui/Spinner";
import { SupportComposer, SupportThread } from "./SupportThread";
import "../../styles/support.css";

/** Polling intervals used only while the live stream is down. */
const POLL_BADGE_MS = 60_000;
const POLL_OPEN_MS = 15_000;

type View = "loading" | "chat" | "new" | "error";

/**
 * Floating "Help" button for the HR panel and the Candidate Portal.
 *
 * It opens a small chat with the platform's support team. A requester has at
 * most one open conversation; once an admin closes it the transcript stays
 * readable and the requester can start a new one. Replies arrive live over
 * the support stream, with polling as a fallback.
 */
export default function HelpWidget({ session }: { session: SessionKind }) {
  const { t } = useLanguage();
  const { notify } = useToast();
  const { pathname } = useLocation();
  const [open, setOpen] = useState(false);
  const [view, setView] = useState<View>("loading");
  const [conversation, setConversation] = useState<SupportConversation | null>(null);
  const [unread, setUnread] = useState(0);
  const buttonRef = useRef<HTMLButtonElement>(null);
  const openRef = useRef(open);
  openRef.current = open;
  const conversationIdRef = useRef<number | null>(null);
  conversationIdRef.current = conversation?.id ?? null;
  /** The requester chose "Start a new conversation": keep the empty form up. */
  const composingRef = useRef(false);

  const refreshUnread = useCallback(() => {
    fetchMySupportUnreadCount(session)
      .then((res) => setUnread(res.unread_count))
      .catch(() => undefined);
  }, [session]);

  /** Load the latest conversation (opening it marks replies as read). */
  const loadLatest = useCallback(async () => {
    try {
      const list = await fetchMySupportConversations(session);
      const latest = list[0];
      if (!latest) {
        setConversation(null);
        setView("new");
      } else {
        setConversation(await fetchMySupportConversation(session, latest.id));
        setView("chat");
      }
      setUnread(0);
    } catch {
      setView((current) => (current === "loading" ? "error" : current));
    }
  }, [session]);

  const handleEvent = useCallback(
    (event: SupportEvent) => {
      if (!openRef.current) {
        refreshUnread();
        return;
      }
      if (composingRef.current) {
        // Only a conversation started elsewhere (another tab) replaces the form.
        if (event.type === "conversation") {
          composingRef.current = false;
          void loadLatest();
        }
        return;
      }
      const currentId = conversationIdRef.current;
      if (currentId === null || event.conversation_id === currentId) void loadLatest();
    },
    [loadLatest, refreshUnread],
  );

  const handleOpenStream = useCallback(() => {
    if (openRef.current && !composingRef.current) void loadLatest();
    else refreshUnread();
  }, [loadLatest, refreshUnread]);

  const { connected } = useSupportStream({
    path: `${supportBase(session)}/stream`,
    session,
    enabled: true,
    onEvent: handleEvent,
    onOpen: handleOpenStream,
    onUnauthorized: () => fetchMySupportUnreadCount(session),
  });

  // Badge on first render, then polling only while the stream is down.
  useEffect(() => {
    refreshUnread();
  }, [refreshUnread]);

  useEffect(() => {
    if (connected) return;
    const poll = () => {
      if (!openRef.current) refreshUnread();
      else if (!composingRef.current) void loadLatest();
    };
    const timer = window.setInterval(poll, open ? POLL_OPEN_MS : POLL_BADGE_MS);
    return () => window.clearInterval(timer);
  }, [connected, open, loadLatest, refreshUnread]);

  useEffect(() => {
    if (!open) {
      composingRef.current = false;
      return;
    }
    setView((current) => (current === "error" ? "loading" : current));
    void loadLatest();
  }, [open, loadLatest]);

  // Escape closes the panel and gives focus back to the button.
  useEffect(() => {
    if (!open) return;
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key !== "Escape") return;
      setOpen(false);
      buttonRef.current?.focus();
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [open]);

  function reportError(error: unknown) {
    const status = error instanceof ApiError ? error.status : 0;
    notify({
      tone: "error",
      title:
        status === 429
          ? t("support.errors.rateLimited")
          : status === 409
            ? t("support.errors.closed")
            : t("support.errors.generic"),
    });
  }

  async function startConversation(body: string) {
    try {
      setConversation(await openSupportConversation(session, body, pathname));
      composingRef.current = false;
      setView("chat");
    } catch (error) {
      reportError(error);
      // 409: an open conversation already exists (e.g. from another tab).
      if (error instanceof ApiError && error.status === 409) {
        composingRef.current = false;
        void loadLatest();
      }
      throw error;
    }
  }

  async function reply(body: string) {
    if (!conversation) return;
    try {
      setConversation(await sendSupportMessage(session, conversation.id, body));
    } catch (error) {
      reportError(error);
      if (error instanceof ApiError && error.status === 409) void loadLatest();
      throw error;
    }
  }

  const closed = conversation?.status === "closed";

  return (
    <>
      {open && (
        <div
          className="help-panel"
          role="dialog"
          aria-modal="false"
          aria-labelledby="help-panel-title"
        >
          <header className="help-panel-header">
            <span className="help-panel-icon" aria-hidden="true">
              <LifeBuoy size={18} />
            </span>
            <div className="help-panel-heading">
              <h2 id="help-panel-title">{t("support.title")}</h2>
              <p>{t("support.subtitle")}</p>
            </div>
            <button
              type="button"
              className="help-panel-close"
              onClick={() => {
                setOpen(false);
                buttonRef.current?.focus();
              }}
              aria-label={t("support.close")}
              title={t("support.close")}
            >
              <X size={18} aria-hidden="true" />
            </button>
          </header>

          {view === "loading" && (
            <div className="help-panel-state">
              <Spinner />
            </div>
          )}

          {view === "error" && (
            <div className="help-panel-state">
              <p>{t("support.errors.load")}</p>
              <button type="button" className="help-link-button" onClick={() => void loadLatest()}>
                {t("support.retry")}
              </button>
            </div>
          )}

          {view === "new" && (
            <>
              <div className="help-panel-intro">
                <p className="help-panel-intro-title">{t("support.newTitle")}</p>
                <p>{t("support.newHint")}</p>
              </div>
              <SupportComposer
                onSend={startConversation}
                placeholder={t("support.describeProblem")}
                autoFocus
              />
            </>
          )}

          {view === "chat" && conversation && (
            <>
              <SupportThread messages={conversation.messages} viewer="requester" />
              {conversation.status === "open" && conversation.messages.every((m) => m.sender === "requester") && (
                <p className="help-panel-note">{t("support.waiting")}</p>
              )}
              {closed ? (
                <div className="help-panel-closed">
                  <p>
                    <Lock size={14} aria-hidden="true" /> {t("support.closedNotice")}
                  </p>
                  <button
                    type="button"
                    className="help-new-button"
                    onClick={() => {
                      composingRef.current = true;
                      setConversation(null);
                      setView("new");
                    }}
                  >
                    <MessageSquarePlus size={16} aria-hidden="true" />
                    {t("support.startNew")}
                  </button>
                </div>
              ) : (
                <SupportComposer onSend={reply} placeholder={t("support.typeMessage")} autoFocus />
              )}
            </>
          )}
        </div>
      )}

      <button
        ref={buttonRef}
        type="button"
        className={`help-fab${open ? " help-fab--open" : ""}`}
        onClick={() => setOpen((value) => !value)}
        aria-expanded={open}
        aria-label={unread > 0 ? `${t("support.button")} (${unread})` : t("support.button")}
      >
        {open ? <X size={20} aria-hidden="true" /> : <LifeBuoy size={20} aria-hidden="true" />}
        <span className="help-fab-label">{t("support.button")}</span>
        {unread > 0 && !open && (
          <span className="help-fab-badge" aria-hidden="true">
            {unread > 9 ? "9+" : unread}
          </span>
        )}
      </button>
    </>
  );
}
