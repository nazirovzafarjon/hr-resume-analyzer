import { describe, expect, it } from "vitest";
import { act, render, screen } from "@testing-library/react";
import { MemoryRouter, useLocation } from "react-router-dom";
import { useUrlFilters } from "./useUrlFilters";

const DEFAULTS = { q: "", status: "", sort: "created_at", order: "desc" };
let api: ReturnType<typeof useUrlFilters<typeof DEFAULTS>>;

function Probe() {
  api = useUrlFilters(DEFAULTS);
  const location = useLocation();
  return <div data-testid="search">{location.search}</div>;
}

function renderAt(url: string) {
  render(
    <MemoryRouter initialEntries={[url]}>
      <Probe />
    </MemoryRouter>,
  );
}

describe("useUrlFilters", () => {
  it("reads filters and page from the URL, falling back to defaults", () => {
    renderAt("/admin/users?status=active&page=3");
    expect(api.values).toEqual({ q: "", status: "active", sort: "created_at", order: "desc" });
    expect(api.page).toBe(3);
    expect(api.active).toBe(true);
  });

  it("ignores an invalid page number", () => {
    renderAt("/admin/users?page=abc");
    expect(api.page).toBe(1);
  });

  it("returns to page 1 when a filter changes and omits defaults", () => {
    renderAt("/admin/users?page=4");
    act(() => api.setFilters({ status: "inactive", sort: "created_at" }));
    expect(screen.getByTestId("search").textContent).toBe("?status=inactive");
  });

  it("does not count sorting as an active filter", () => {
    renderAt("/admin/users?sort=name&order=asc");
    expect(api.active).toBe(false);
  });

  it("clears everything", () => {
    renderAt("/admin/users?q=anna&status=active&page=2");
    act(() => api.clear());
    expect(screen.getByTestId("search").textContent).toBe("");
  });
});
