import { API_BASE_URL } from "./config";

export type ContactPayload = {
  first_name: string;
  last_name: string;
  email: string;
  message: string;
};

/** Why a submission failed, mapped to a translated message by the form. */
export type ContactErrorKind = "network" | "validation" | "rateLimited" | "server";

export class ContactError extends Error {
  constructor(readonly kind: ContactErrorKind) {
    super(kind);
  }
}

/** POST /api/public/contact — public, so no token is ever attached. */
export async function sendContactMessage(payload: ContactPayload): Promise<void> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}/public/contact`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  } catch {
    // fetch only throws on network/CORS failures.
    throw new ContactError("network");
  }

  if (response.ok) return;
  if (response.status === 422) throw new ContactError("validation");
  if (response.status === 429) throw new ContactError("rateLimited");
  throw new ContactError("server");
}
