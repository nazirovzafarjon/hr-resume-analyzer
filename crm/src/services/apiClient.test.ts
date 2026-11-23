import { afterEach, describe, expect, it, vi } from "vitest";
import { apiRequest } from "./apiClient";
import { getRefreshToken, getToken, saveTokens } from "../auth/tokenStorage";

type Reply = [number, unknown];
type Step = Reply | "network-error" | (() => Reply);

/** Replay `steps` in order; a function step runs a side effect and returns its reply. */
function stubFetch(steps: Step[]) {
  const calls: { url: string; auth?: string }[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init?: RequestInit) => {
      calls.push({ url, auth: (init?.headers as Record<string, string> | undefined)?.Authorization });
      const step = steps.shift() ?? [500, {}];
      if (step === "network-error") throw new TypeError("Failed to fetch");
      const [status, body] = typeof step === "function" ? step() : step;
      return new Response(JSON.stringify(body), { status });
    }),
  );
  return calls;
}

function listenForSignOut() {
  const events: string[] = [];
  const handler = () => events.push("signed-out");
  window.addEventListener("auth:unauthorized", handler);
  return { events, stop: () => window.removeEventListener("auth:unauthorized", handler) };
}

afterEach(() => {
  localStorage.clear();
  vi.unstubAllGlobals();
});

describe("token refresh in the API client", () => {
  it("keeps the session when the refresh request cannot reach the server", async () => {
    saveTokens("old-access", "old-refresh");
    stubFetch([[401, { detail: "expired" }], "network-error"]);
    const signOut = listenForSignOut();

    await expect(apiRequest("/jobs", { auth: true })).rejects.toMatchObject({ status: 0 });

    signOut.stop();
    expect(signOut.events).toEqual([]);
    expect([getToken(), getRefreshToken()]).toEqual(["old-access", "old-refresh"]);
  });

  it("keeps the session when the refresh endpoint answers 5xx", async () => {
    saveTokens("old-access", "old-refresh");
    stubFetch([[401, {}], [503, {}]]);
    const signOut = listenForSignOut();

    await expect(apiRequest("/jobs", { auth: true })).rejects.toMatchObject({ status: 0 });

    signOut.stop();
    expect(signOut.events).toEqual([]);
    expect(getToken()).toBe("old-access");
  });

  it("signs out when the server rejects the refresh token", async () => {
    saveTokens("old-access", "old-refresh");
    stubFetch([[401, {}], [401, {}]]);
    const signOut = listenForSignOut();

    await expect(apiRequest("/jobs", { auth: true })).rejects.toMatchObject({ status: 401 });

    signOut.stop();
    expect(signOut.events).toEqual(["signed-out"]);
    expect(getToken()).toBeNull();
  });

  it("uses a token another tab already refreshed instead of spending the refresh token", async () => {
    saveTokens("old-access", "old-refresh");
    // While the first request is in flight another tab rotates the pair, so
    // this tab's token comes back 401 although a valid one is now stored.
    const calls = stubFetch([
      () => {
        saveTokens("tab2-access", "tab2-refresh");
        return [401, { detail: "expired" }];
      },
      [200, { ok: true }],
    ]);

    await expect(apiRequest("/jobs", { auth: true })).resolves.toEqual({ ok: true });

    expect(calls.map((call) => call.url).some((url) => url.endsWith("/auth/refresh"))).toBe(false);
    expect(calls[1].auth).toBe("Bearer tab2-access");
    expect(getRefreshToken()).toBe("tab2-refresh");
  });
});
