/**
 * Telegram account linking (`/api/telegram/{hr|candidate}/*`).
 *
 * `kind` picks both the endpoint and the API session: HR pages use the HR
 * session, Candidate Portal pages the candidate session.
 */
import { apiRequest } from "./apiClient";

export type TelegramKind = "hr" | "candidate";

export type TelegramLinkStatus = {
  /** False when the server has no bot configured. */
  enabled: boolean;
  linked: boolean;
  bot_username: string | null;
  username: string | null;
  first_name: string | null;
  linked_at: string | null;
  /** False after the user blocked the bot in Telegram. */
  is_active: boolean | null;
};

export type TelegramLinkToken = {
  deep_link: string;
  expires_at: string;
};

function options(kind: TelegramKind) {
  return { auth: true, session: kind === "hr" ? "hr" : "candidate" } as const;
}

/** GET — is the bot available and is this account linked? */
export function getTelegramLink(kind: TelegramKind): Promise<TelegramLinkStatus> {
  return apiRequest(`/telegram/${kind}/link`, options(kind));
}

/** POST — a single-use `t.me/<bot>?start=<token>` link (valid a few minutes). */
export function createTelegramLinkToken(kind: TelegramKind): Promise<TelegramLinkToken> {
  return apiRequest(`/telegram/${kind}/link-token`, { ...options(kind), method: "POST" });
}

/** DELETE — disconnect Telegram from this account. */
export function deleteTelegramLink(kind: TelegramKind): Promise<void> {
  return apiRequest(`/telegram/${kind}/link`, { ...options(kind), method: "DELETE" });
}
