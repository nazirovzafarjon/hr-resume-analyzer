import { CANDIDATE_HOME } from "../../context/CandidateAuthContext";

/**
 * Where to go after a candidate signs in: the `next` query value when it is a
 * same-site path (e.g. back to /apply/<token>), otherwise the portal home.
 * Absolute and protocol-relative URLs are ignored (no open redirect).
 */
export function safeNext(next: string | null): string {
  if (!next || !next.startsWith("/") || next.startsWith("//") || next.startsWith("/\\")) return CANDIDATE_HOME;
  return next;
}
