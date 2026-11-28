import { useCallback, useEffect, useRef } from "react";
import { useLocation } from "react-router-dom";
import { useLanguage } from "../../contexts/LanguageContext";
import { useToast } from "../../contexts/ToastContext";
import { useSupportStream } from "../../hooks/useSupportStream";
import { fetchAdminSupportUnreadCount } from "../../services/supportService";
import type { SupportEvent } from "../../types/support";
import {
  SUPPORT_ADMIN_EVENT,
  UNREAD_REFRESH_EVENT,
  publishAdminSupportUnread,
} from "./adminSupportBus";

const POLL_MS = 60_000;

/**
 * The admin console's single live connection to the support stream.
 *
 * Mounted once in the admin shell: keeps the Support nav badge current,
 * forwards events to the inbox page, and shows a toast when a new message
 * arrives while the admin is elsewhere in the console. Renders nothing.
 */
export default function AdminSupportLive() {
  const { t } = useLanguage();
  const { notify } = useToast();
  const { pathname } = useLocation();
  const pathnameRef = useRef(pathname);
  pathnameRef.current = pathname;
  const previous = useRef<number | null>(null);

  const refresh = useCallback(() => {
    fetchAdminSupportUnreadCount()
      .then(({ unread_count: count }) => {
        const before = previous.current;
        previous.current = count;
        publishAdminSupportUnread(count);
        if (before !== null && count > before && !pathnameRef.current.startsWith("/admin/support")) {
          notify({
            tone: "info",
            title: t("support.admin.newMessageToast"),
            message: t("support.admin.newMessageHint"),
          });
        }
      })
      .catch(() => undefined);
  }, [notify, t]);

  const handleEvent = useCallback(
    (event: SupportEvent) => {
      refresh();
      window.dispatchEvent(new CustomEvent<SupportEvent>(SUPPORT_ADMIN_EVENT, { detail: event }));
    },
    [refresh],
  );

  const { connected } = useSupportStream({
    path: "/admin/support/stream",
    session: "hr",
    enabled: true,
    onEvent: handleEvent,
    onOpen: refresh,
    onUnauthorized: fetchAdminSupportUnreadCount,
  });

  useEffect(() => {
    refresh();
    window.addEventListener(UNREAD_REFRESH_EVENT, refresh);
    return () => window.removeEventListener(UNREAD_REFRESH_EVENT, refresh);
  }, [refresh]);

  useEffect(() => {
    if (connected) return;
    const timer = window.setInterval(refresh, POLL_MS);
    return () => window.clearInterval(timer);
  }, [connected, refresh]);

  return null;
}
