import { describe, expect, it, vi } from "vitest";
import { useEffect, useState, type ReactNode } from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import RoleSelectPage from "./RoleSelectPage";
import { AuthProvider, useAuth } from "../../context/AuthContext";
import { ThemeProvider } from "../../contexts/ThemeContext";
import { LanguageProvider } from "../../contexts/LanguageContext";
import { ToastProvider } from "../../contexts/ToastContext";
import { ApiError } from "../../utils/apiError";
import { LocationProbe, fakeJwt } from "../../test/utils";
import type { RoleSelectionRequired, SessionRole } from "../../types/auth";

vi.mock("../../services/authService", () => ({
  selectRole: vi.fn(),
  switchRole: vi.fn(),
}));

import * as authService from "../../services/authService";

/**
 * Seeds the pending choice (as the login page does) before the routes mount,
 * so the page sees it on its first render.
 */
function Seed({ result, children }: { result?: RoleSelectionRequired; children: ReactNode }) {
  const { completeSignIn } = useAuth();
  const [ready, setReady] = useState(false);
  useEffect(() => {
    if (result) completeSignIn(result);
    setReady(true);
    // Runs once per test tree: completeSignIn is stable and each test
    // passes a fresh result, so no dependencies are needed.
  }, []);
  return ready ? <>{children}</> : null;
}

function renderPage(overrides: Partial<RoleSelectionRequired> | null = {}) {
  const result: RoleSelectionRequired | undefined =
    overrides === null
      ? undefined
      : {
          requires_role_selection: true,
          selection_token: "selection-token",
          available_roles: ["user", "admin"],
          full_name: "Zafarjon Nazirov",
          expires_in: 300,
          ...overrides,
        };
  render(
    <MemoryRouter initialEntries={["/select-role"]}>
      <AuthProvider>
        <ThemeProvider>
          <LanguageProvider>
            <ToastProvider>
              <Seed result={result}>
                <Routes>
                  <Route path="/select-role" element={<RoleSelectPage />} />
                  <Route path="*" element={<LocationProbe />} />
                </Routes>
              </Seed>
            </ToastProvider>
          </LanguageProvider>
        </ThemeProvider>
      </AuthProvider>
    </MemoryRouter>,
  );
}

function session(role: SessionRole) {
  return { access_token: fakeJwt({ role }), refresh_token: "r", token_type: "bearer" };
}

describe("RoleSelectPage", () => {
  it("redirects to login when there is nothing to choose", () => {
    renderPage(null);
    expect(screen.getByTestId("location").textContent).toBe("/login");
  });

  it("greets the user and offers both workspaces", async () => {
    renderPage();
    expect(await screen.findByText("Welcome back, Zafarjon")).toBeTruthy();
    expect(screen.getByRole("button", { name: /Continue as HR/ })).toBeTruthy();
    expect(screen.getByRole("button", { name: /Continue as Admin/ })).toBeTruthy();
  });

  it("only offers workspaces the server listed", async () => {
    renderPage({ available_roles: ["user"] });
    await screen.findByRole("button", { name: /Continue as HR/ });
    expect(screen.queryByRole("button", { name: /Continue as Admin/ })).toBeNull();
  });

  it.each([
    ["HR", "user", "/dashboard"],
    ["Admin", "admin", "/admin/dashboard"],
  ] as const)("continues as %s", async (label, role, target) => {
    vi.mocked(authService.selectRole).mockResolvedValueOnce(session(role));
    renderPage();
    fireEvent.click(await screen.findByRole("button", { name: new RegExp(`Continue as ${label}`) }));
    expect(await screen.findByTestId("location")).toBeTruthy();
    expect(screen.getByTestId("location").textContent).toBe(target);
    expect(authService.selectRole).toHaveBeenCalledWith("selection-token", role);
  });

  it("explains when the workspace is not available", async () => {
    vi.mocked(authService.selectRole).mockRejectedValueOnce(new ApiError(403, "forbidden"));
    renderPage();
    fireEvent.click(await screen.findByRole("button", { name: /Continue as Admin/ }));
    expect(await screen.findByText(/This workspace is not available for your account/)).toBeTruthy();
    // Still on the choice; nothing was stored.
    expect(screen.queryByTestId("location")).toBeNull();
  });

  it("asks to sign in again when the choice expired", async () => {
    vi.mocked(authService.selectRole).mockRejectedValueOnce(new ApiError(401, "expired"));
    renderPage();
    fireEvent.click(await screen.findByRole("button", { name: /Continue as HR/ }));
    expect(await screen.findByText(/Your session has expired/)).toBeTruthy();
    fireEvent.click(screen.getAllByRole("button", { name: /Sign in again/ })[0]!);
    expect(screen.getByTestId("location").textContent).toBe("/login");
  });

  it("disables the options once the selection token has expired", async () => {
    renderPage({ expires_in: -1 });
    const hr = await screen.findByRole("button", { name: /Continue as HR/ });
    expect((hr as HTMLButtonElement).disabled).toBe(true);
  });
});
