import { afterEach, describe, expect, it, vi } from "vitest";
import { fetchCandidateDashboard } from "./candidatePortalService";
import { submitPublicApplication } from "./publicService";
import {
  getCandidateRefreshToken,
  getCandidateToken,
  getRefreshToken,
  getToken,
  saveCandidateTokens,
  saveTokens,
} from "../auth/tokenStorage";

type Call = { url: string; headers: Record<string, string> };

/** Queue of responses; records url + headers of every request. */
function stubFetch(responses: Array<[number, unknown]>) {
  const calls: Call[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init?: RequestInit) => {
      calls.push({ url, headers: (init?.headers ?? {}) as Record<string, string> });
      const [status, body] = responses.shift() ?? [500, {}];
      return new Response(JSON.stringify(body), { status });
    }),
  );
  return calls;
}

afterEach(() => localStorage.clear());

describe("candidate session in the shared API client", () => {
  it("uses the candidate token, never the HR one", async () => {
    saveTokens("hr-access", "hr-refresh");
    saveCandidateTokens("cand-access", "cand-refresh");
    const calls = stubFetch([[200, {}]]);
    await fetchCandidateDashboard();
    expect(calls[0].url).toMatch(/\/candidate\/dashboard$/);
    expect(calls[0].headers.Authorization).toBe("Bearer cand-access");
  });

  it("refreshes through the candidate endpoint and keeps the HR session", async () => {
    saveTokens("hr-access", "hr-refresh");
    saveCandidateTokens("old-access", "old-refresh");
    const calls = stubFetch([
      [401, { detail: "expired" }],
      [200, { access_token: "new-access", refresh_token: "new-refresh" }],
      [200, {}],
    ]);
    await fetchCandidateDashboard();
    expect(calls[1].url).toMatch(/\/candidate\/auth\/refresh$/);
    expect(calls[2].headers.Authorization).toBe("Bearer new-access");
    expect(getCandidateToken()).toBe("new-access");
    expect(getCandidateRefreshToken()).toBe("new-refresh");
    expect([getToken(), getRefreshToken()]).toEqual(["hr-access", "hr-refresh"]);
  });

  it("drops only the candidate session when it cannot be refreshed", async () => {
    saveTokens("hr-access", "hr-refresh");
    saveCandidateTokens("old-access", "old-refresh");
    const events: string[] = [];
    const onCandidate = () => events.push("candidate");
    const onHr = () => events.push("hr");
    window.addEventListener("candidate:unauthorized", onCandidate);
    window.addEventListener("auth:unauthorized", onHr);
    stubFetch([
      [401, {}],
      [401, {}],
    ]);
    await expect(fetchCandidateDashboard()).rejects.toMatchObject({ status: 401 });
    window.removeEventListener("candidate:unauthorized", onCandidate);
    window.removeEventListener("auth:unauthorized", onHr);
    expect(events).toEqual(["candidate"]);
    expect(getCandidateToken()).toBeNull();
    expect(getToken()).toBe("hr-access");
  });

  it("public application submit sends the candidate token only when signed in", async () => {
    let calls = stubFetch([[201, {}]]);
    await submitPublicApplication("tok", [], {}, {});
    expect(calls[0].headers.Authorization).toBeUndefined();

    saveTokens("hr-access", "hr-refresh");
    calls = stubFetch([[201, {}]]);
    await submitPublicApplication("tok", [], {}, {});
    expect(calls[0].headers.Authorization).toBeUndefined();

    saveCandidateTokens("cand-access", "cand-refresh");
    calls = stubFetch([[201, {}]]);
    await submitPublicApplication("tok", [], {}, {});
    expect(calls[0].headers.Authorization).toBe("Bearer cand-access");
  });
});
