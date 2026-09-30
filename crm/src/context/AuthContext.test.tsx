import { describe, expect, it, vi } from "vitest";
import { act, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { AuthProvider, landingPath, useAuth } from "./AuthContext";
import { getRefreshToken, getToken } from "../auth/tokenStorage";
import { fakeJwt } from "../test/utils";
import type { SignInResult } from "../types/auth";

vi.mock("../services/authService", () => ({
  selectRole: vi.fn(async (_token: string, role: string) => ({
    access_token: fakeJwt({ role }),
    refresh_token: `refresh-${role}`,
    token_type: "bearer",
  })),
  switchRole: vi.fn(async (role: string) => ({
    access_token: fakeJwt({ role }),
    refresh_token: `switched-${role}`,
    token_type: "bearer",
  })),
}));

import * as authService from "../services/authService";

let api: ReturnType<typeof useAuth>;
function Capture() {
  api = useAuth();
  return (
    <div>
      <span data-testid="role">{api.activeRole ?? "none"}</span>
      <span data-testid="pending">{api.pendingSelection ? "pending" : "none"}</span>
    </div>
  );
}

function renderAuth() {
  render(
    <MemoryRouter>
      <AuthProvider>
        <Capture />
      </AuthProvider>
    </MemoryRouter>,
  );
}

const selection: SignInResult = {
  requires_role_selection: true,
  selection_token: "selection-token",
  available_roles: ["user", "admin"],
  full_name: "Zafarjon Test",
  expires_in: 300,
};

describe("AuthContext", () => {
  it("enters the HR workspace directly for a single-role sign-in", () => {
    renderAuth();
    let next = "";
    act(() => {
      next = api.completeSignIn({ access_token: fakeJwt({ role: "user" }), refresh_token: "r", token_type: "bearer" });
    });
    expect(next).toBe("/dashboard");
    expect(screen.getByTestId("role").textContent).toBe("user");
    expect(getRefreshToken()).toBe("r");
  });

  it("stores nothing and asks for a workspace when the account has several", () => {
    renderAuth();
    let next = "";
    act(() => {
      next = api.completeSignIn(selection);
    });
    expect(next).toBe("/select-role");
    expect(getToken()).toBeNull();
    expect(screen.getByTestId("role").textContent).toBe("none");
    expect(screen.getByTestId("pending").textContent).toBe("pending");
    // The selection token is kept in memory only.
    expect(JSON.stringify({ ...localStorage })).not.toContain("selection-token");
    expect(JSON.stringify({ ...sessionStorage })).not.toContain("selection-token");
  });

  it("finishes the sign-in in the chosen workspace", async () => {
    renderAuth();
    act(() => {
      api.completeSignIn(selection);
    });
    let next = "";
    await act(async () => {
      next = await api.selectRole("admin");
    });
    expect(authService.selectRole).toHaveBeenCalledWith("selection-token", "admin");
    expect(next).toBe("/admin/dashboard");
    expect(screen.getByTestId("role").textContent).toBe("admin");
    expect(screen.getByTestId("pending").textContent).toBe("none");
  });

  it("switches workspace through the server and replaces the tokens", async () => {
    renderAuth();
    act(() => {
      api.signIn({ access_token: fakeJwt({ role: "user" }), refresh_token: "old", token_type: "bearer" });
    });
    let next = "";
    await act(async () => {
      next = await api.switchRole("admin");
    });
    expect(authService.switchRole).toHaveBeenCalledWith("admin");
    expect(next).toBe("/admin/dashboard");
    expect(getRefreshToken()).toBe("switched-admin");
  });

  it("derives the workspace from the token, not from other storage", () => {
    localStorage.setItem("role", "admin");
    sessionStorage.setItem("activeRole", "admin");
    renderAuth();
    act(() => {
      api.signIn({ access_token: fakeJwt({ role: "user" }), token_type: "bearer" });
    });
    expect(screen.getByTestId("role").textContent).toBe("user");
  });

  it("clears the session and any pending choice on sign-out", () => {
    renderAuth();
    act(() => {
      api.completeSignIn(selection);
    });
    act(() => api.signOut());
    expect(screen.getByTestId("pending").textContent).toBe("none");
    act(() => {
      api.signIn({ access_token: fakeJwt({ role: "admin" }), refresh_token: "r", token_type: "bearer" });
    });
    act(() => api.signOut());
    expect(getToken()).toBeNull();
    expect(getRefreshToken()).toBeNull();
    expect(screen.getByTestId("role").textContent).toBe("none");
  });

  it("drops the session when the API reports it as dead", () => {
    renderAuth();
    act(() => {
      api.signIn({ access_token: fakeJwt({ role: "admin" }), token_type: "bearer" });
    });
    act(() => {
      window.dispatchEvent(new Event("auth:unauthorized"));
    });
    expect(screen.getByTestId("role").textContent).toBe("none");
  });

  it("maps workspaces to their landing pages", () => {
    expect(landingPath("admin")).toBe("/admin/dashboard");
    expect(landingPath("user")).toBe("/dashboard");
    expect(landingPath(null)).toBe("/dashboard");
  });
});
