/** Help Center support chat (see backend app/routers/support.py). */

export type SupportStatus = "open" | "closed";
export type SupportSender = "requester" | "admin";
export type SupportRequesterKind = "hr" | "candidate";

export type SupportMessage = {
  id: number;
  sender: SupportSender;
  author_name: string | null;
  body: string;
  created_at: string;
};

export type SupportConversationSummary = {
  id: number;
  status: SupportStatus;
  created_at: string;
  last_message_at: string;
  closed_at: string | null;
  unread_count: number;
};

export type SupportConversation = SupportConversationSummary & {
  messages: SupportMessage[];
};

export type SupportAdminRow = {
  id: number;
  status: SupportStatus;
  requester_kind: SupportRequesterKind;
  requester_name: string;
  requester_email: string;
  preview: string;
  message_count: number;
  unread_count: number;
  created_at: string;
  last_message_at: string;
  closed_at: string | null;
};

export type SupportAdminConversation = SupportAdminRow & {
  page_url: string | null;
  closed_by_name: string | null;
  requester_id: number | null;
  messages: SupportMessage[];
};

export type SupportAdminPage = {
  items: SupportAdminRow[];
  total: number;
  page: number;
  limit: number;
};

/** Live-update notice pushed over the support stream. */
export type SupportEvent = {
  type: "conversation" | "message" | "closed" | "read";
  conversation_id: number;
};
