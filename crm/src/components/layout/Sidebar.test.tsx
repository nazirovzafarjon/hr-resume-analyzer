import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, screen, waitFor } from "@testing-library/react";
import Sidebar from "./Sidebar";
import { saveTokens } from "../../auth/tokenStorage";
import { invalidateCurrentUser } from "../../hooks/useCurrentUser";
import { fakeJwt, renderWithProviders } from "../../test/utils";
import type { SessionRole } from "../../types/auth";
import type { UserProfile } from "../../types/user";

vi.mock("../../services/settingsService", () => ({ getCurrentUser: vi.fn() }));
vi.mock("../../services/authService", () => ({ switchRole: vi.fn() }));

import { getCurrentUser } from "../../services/settingsService";
import { switchRole } from "../../services/authService";

function signedInAs(sessionRole: SessionRole, accountRoles: SessionRole[]) {
  saveTokens(fakeJwt({ role: sessionRole }), "refresh");
  vi.mocked(getCurrentUser).mockResolvedValue({
    id: 1,
    email: "admin@example.com",
    full_name: "Admin",
    is_superuser: accountRoles.includes("admin"),
    available_roles: accountRoles,
    active_role: sessionRole,
  } as UserProfile);
}

function renderSidebar() {
  renderWithProviders(
    <Sidebar open={false} collapsed={false} onClose={vi.fn()} onToggleCollapse={vi.fn()} />,
    { path: "/dashboard" },
  );
}

describe("Sidebar admin group", () => {
  beforeEach(() => {
    invalidateCurrentUser();
    vi.mocked(getCurrentUser).mockReset();
    vi.mocked(switchRole).mockReset();
  });

  it("is hidden from a regular HR account", async () => {
    signedInAs("user", ["user"]);
    renderSidebar();
    await screen.findByText("Dashboard");
    await waitFor(() => expect(getCurrentUser).toHaveBeenCalled());
    expect(screen.queryByText("Admin")).toBeNull();
    expect(screen.queryByText("HR Users")).toBeNull();
  });

  it("offers HR Users as plain links in an admin session", async () => {
    signedInAs("admin", ["user", "admin"]);
    renderSidebar();
    const users = await screen.findByRole("link", { name: "HR Users" });
    expect(users.getAttribute("href")).toBe("/admin/users");
  });

  it("asks the server to switch workspace from an HR session, then opens HR Users", async () => {
    signedInAs("user", ["user", "admin"]);
    vi.mocked(switchRole).mockResolvedValueOnce({
      access_token: fakeJwt({ role: "admin" }),
      refresh_token: "r",
      token_type: "bearer",
    } as never);
    renderSidebar();
    fireEvent.click(await screen.findByRole("button", { name: "HR Users" }));
    await waitFor(() => expect(screen.getByTestId("location").textContent).toBe("/admin/users"));
    expect(switchRole).toHaveBeenCalledWith("admin");
  });
});
