import { apiRequest, type SessionKind } from "./apiClient";
import type {
  SupportAdminConversation,
  SupportAdminPage,
  SupportConversation,
  SupportConversationSummary,
} from "../types/support";

/**
 * Help Center support chat.
 *
 * The requester side exists twice on the backend (HR: /support, Candidate
 * Portal: /candidate/support) with the same shape; `session` picks which one,
 * and with it which stored tokens are sent.
 */
export function supportBase(session: SessionKind): string {
  return session === "candidate" ? "/candidate/support" : "/support";
}

export function fetchMySupportConversations(session: SessionKind): Promise<SupportConversationSummary[]> {
  return apiRequest(`${supportBase(session)}/conversations`, { auth: true, session });
}

export function fetchMySupportUnreadCount(session: SessionKind): Promise<{ unread_count: number }> {
  return apiRequest(`${supportBase(session)}/unread-count`, { auth: true, session });
}

export function fetchMySupportConversation(session: SessionKind, id: number): Promise<SupportConversation> {
  return apiRequest(`${supportBase(session)}/conversations/${id}`, { auth: true, session });
}

export function openSupportConversation(
  session: SessionKind,
  body: string,
  pageUrl: string | null,
): Promise<SupportConversation> {
  return apiRequest(`${supportBase(session)}/conversations`, {
    method: "POST",
    auth: true,
    session,
    body: { body, page_url: pageUrl },
  });
}

export function sendSupportMessage(session: SessionKind, id: number, body: string): Promise<SupportConversation> {
  return apiRequest(`${supportBase(session)}/conversations/${id}/messages`, {
    method: "POST",
    auth: true,
    session,
    body: { body },
  });
}

// --- Admin inbox -----------------------------------------------------------

export type SupportAdminFilters = {
  status?: "open" | "closed";
  kind?: "hr" | "candidate";
  q?: string;
  page?: number;
  limit?: number;
};

export function fetchAdminSupportConversations(filters: SupportAdminFilters): Promise<SupportAdminPage> {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(filters)) {
    if (value !== undefined && value !== "") params.set(key, String(value));
  }
  const query = params.toString();
  return apiRequest(`/admin/support/conversations${query ? `?${query}` : ""}`, { auth: true });
}

export function fetchAdminSupportUnreadCount(): Promise<{ unread_count: number }> {
  return apiRequest("/admin/support/unread-count", { auth: true });
}

export function fetchAdminSupportConversation(id: number): Promise<SupportAdminConversation> {
  return apiRequest(`/admin/support/conversations/${id}`, { auth: true });
}

export function replyToSupportConversation(id: number, body: string): Promise<SupportAdminConversation> {
  return apiRequest(`/admin/support/conversations/${id}/messages`, {
    method: "POST",
    auth: true,
    body: { body },
  });
}

export function closeSupportConversation(id: number): Promise<SupportAdminConversation> {
  return apiRequest(`/admin/support/conversations/${id}/close`, { method: "POST", auth: true });
}
