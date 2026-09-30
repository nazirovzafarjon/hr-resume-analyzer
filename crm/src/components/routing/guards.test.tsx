import { describe, expect, it } from "vitest";
import { screen } from "@testing-library/react";
import RequireAdmin from "./RequireAdmin";
import RequireAuth from "./RequireAuth";
import { saveTokens } from "../../auth/tokenStorage";
import { fakeJwt, renderWithProviders } from "../../test/utils";

const secret = <div>admin console</div>;

describe("RequireAdmin", () => {
  it("sends visitors without a session to login", () => {
    renderWithProviders(<RequireAdmin>{secret}</RequireAdmin>, { path: "/admin/users" });
    expect(screen.getByTestId("location").textContent).toBe("/login");
    expect(screen.queryByText("admin console")).toBeNull();
  });

  it("keeps an HR session out of the console", () => {
    saveTokens(fakeJwt({ role: "user" }), null);
    renderWithProviders(<RequireAdmin>{secret}</RequireAdmin>, { path: "/admin/users" });
    expect(screen.getByTestId("location").textContent).toBe("/dashboard");
    expect(screen.queryByText("admin console")).toBeNull();
  });

  it("ignores role hints in storage and the URL", () => {
    saveTokens(fakeJwt({ role: "user" }), null);
    localStorage.setItem("role", "admin");
    sessionStorage.setItem("role", "admin");
    renderWithProviders(<RequireAdmin>{secret}</RequireAdmin>, {
      path: "/admin/users?role=admin&is_superuser=true",
    });
    expect(screen.getByTestId("location").textContent).toBe("/dashboard");
  });

  it("treats a legacy token without a workspace as HR", () => {
    saveTokens(fakeJwt({}), null);
    renderWithProviders(<RequireAdmin>{secret}</RequireAdmin>, { path: "/admin/users" });
    expect(screen.getByTestId("location").textContent).toBe("/dashboard");
  });

  it("renders for an admin session", () => {
    saveTokens(fakeJwt({ role: "admin" }), null);
    renderWithProviders(<RequireAdmin>{secret}</RequireAdmin>, { path: "/admin/users" });
    expect(screen.getByText("admin console")).toBeTruthy();
  });
});

describe("RequireAuth", () => {
  it("sends visitors without a session to login", () => {
    renderWithProviders(<RequireAuth>{secret}</RequireAuth>, { path: "/dashboard" });
    expect(screen.getByTestId("location").textContent).toBe("/login");
  });

  it("renders for any session", () => {
    saveTokens(fakeJwt({ role: "user" }), null);
    renderWithProviders(<RequireAuth>{secret}</RequireAuth>, { path: "/dashboard" });
    expect(screen.getByText("admin console")).toBeTruthy();
  });
});
