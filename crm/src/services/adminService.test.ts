import { describe, expect, it, vi } from "vitest";
import { fetchAdminUsers, updateAdminSettings } from "./adminService";
import { saveTokens } from "../auth/tokenStorage";
import { fakeJwt } from "../test/utils";

function stubFetch(body: unknown = { items: [], total: 0, page: 1, limit: 25 }) {
  const fetchMock = vi.fn(async (_url: string, _init?: RequestInit) => new Response(JSON.stringify(body), { status: 200 }));
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

describe("adminService", () => {
  it("drops empty filters so 'All' sends nothing", async () => {
    saveTokens(fakeJwt({ role: "admin" }), null);
    const fetchMock = stubFetch();
    await fetchAdminUsers({ q: "", status: "active", role: undefined, page: 2, limit: 25, sort: null });
    const url = new URL(String(fetchMock.mock.calls[0]?.[0]));
    expect(url.pathname).toMatch(/\/admin\/users$/);
    expect(Object.fromEntries(url.searchParams)).toEqual({ status: "active", page: "2", limit: "25" });
  });

  it("encodes search text safely", async () => {
    saveTokens(fakeJwt({ role: "admin" }), null);
    const fetchMock = stubFetch();
    await fetchAdminUsers({ q: "a&b=c %" });
    const url = new URL(String(fetchMock.mock.calls[0]?.[0]));
    expect(url.searchParams.get("q")).toBe("a&b=c %");
  });

  it("only ever sends the runtime switch when saving settings", async () => {
    saveTokens(fakeJwt({ role: "admin" }), null);
    const fetchMock = stubFetch({});
    await updateAdminSettings({ registration_enabled: false });
    const [, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(init.method).toBe("PATCH");
    expect(JSON.parse(String(init.body))).toEqual({ registration_enabled: false });
  });
});
