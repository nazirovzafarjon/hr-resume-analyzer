import { afterEach, describe, expect, it, vi } from "vitest";
import { selectRole, switchRole, logout } from "./authService";
import { saveTokens } from "../auth/tokenStorage";
import { fakeJwt } from "../test/utils";

function mockFetch(status = 200, body: unknown = {}) {
  const fetchMock = vi.fn(async (_url: string, _init?: RequestInit) => new Response(JSON.stringify(body), { status }));
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function lastCall(fetchMock: ReturnType<typeof mockFetch>) {
  const [url, init] = fetchMock.mock.calls[fetchMock.mock.calls.length - 1] as [string, RequestInit];
  return { url, init, headers: init.headers as Record<string, string>, body: JSON.parse(String(init.body ?? "null")) };
}

afterEach(() => localStorage.clear());

describe("workspace requests", () => {
  it("sends the selection token in the body and never as a bearer token", async () => {
    // Even with an old session in storage, the selection call is unauthenticated.
    saveTokens(fakeJwt({ role: "user" }), "refresh");
    const fetchMock = mockFetch(200, { access_token: fakeJwt({ role: "admin" }), token_type: "bearer" });
    await selectRole("selection-token", "admin");
    const call = lastCall(fetchMock);
    expect(call.url).toMatch(/\/auth\/select-role$/);
    expect(call.body).toEqual({ role: "admin", selection_token: "selection-token" });
    expect(call.headers.Authorization).toBeUndefined();
  });

  it("does not retry a rejected selection with a token refresh", async () => {
    saveTokens(fakeJwt({ role: "user" }), "refresh");
    const fetchMock = mockFetch(401, { detail: "Your sign-in has expired. Please sign in again." });
    await expect(selectRole("expired", "user")).rejects.toMatchObject({ status: 401 });
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("switches workspace with the current session", async () => {
    const access = fakeJwt({ role: "user" });
    saveTokens(access, "refresh");
    const fetchMock = mockFetch(200, { access_token: fakeJwt({ role: "admin" }), token_type: "bearer" });
    await switchRole("admin");
    const call = lastCall(fetchMock);
    expect(call.body).toEqual({ role: "admin" });
    expect(call.headers.Authorization).toBe(`Bearer ${access}`);
  });

  it("sends the refresh token on logout so the server can revoke it", async () => {
    saveTokens(fakeJwt({}), "the-refresh-token");
    const fetchMock = vi.fn(async (_url: string, _init?: RequestInit) => new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetchMock);
    await logout("the-refresh-token");
    const [, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(JSON.parse(String(init.body))).toEqual({ refresh_token: "the-refresh-token" });
  });
});
