import { useEffect, useState } from "react";

/**
 * Window events that connect the admin console's single support stream
 * (AdminSupportLive) to the Support nav badge and the inbox page.
 */

/** Every support stream event, re-broadcast with the event as `detail`. */
export const SUPPORT_ADMIN_EVENT = "support:admin-event";
const UNREAD_EVENT = "support:admin-unread";
export const UNREAD_REFRESH_EVENT = "support:admin-unread-refresh";

let lastUnread: number | null = null;

export function publishAdminSupportUnread(count: number) {
  lastUnread = count;
  window.dispatchEvent(new CustomEvent<number>(UNREAD_EVENT, { detail: count }));
}

/** Number of support conversations with unread messages (for the nav badge). */
export function useAdminSupportUnread(): number | null {
  const [count, setCount] = useState<number | null>(lastUnread);
  useEffect(() => {
    const handle = (event: Event) => setCount((event as CustomEvent<number>).detail);
    window.addEventListener(UNREAD_EVENT, handle);
    return () => window.removeEventListener(UNREAD_EVENT, handle);
  }, []);
  return count;
}

/** Ask the live connection to reload the unread count (e.g. after reading a chat). */
export function requestAdminSupportUnreadRefresh() {
  window.dispatchEvent(new Event(UNREAD_REFRESH_EVENT));
}
