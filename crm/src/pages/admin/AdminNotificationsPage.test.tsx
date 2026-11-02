import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, screen, waitFor } from "@testing-library/react";
import AdminNotificationsPage from "./AdminNotificationsPage";
import { renderWithProviders } from "../../test/utils";
import * as adminService from "../../services/adminService";
import type { ContactNotificationPage, ContactNotificationRow } from "../../types/admin";

vi.mock("../../services/adminService", () => ({
  fetchAdminNotifications: vi.fn(),
  fetchAdminUnreadNotificationsCount: vi.fn(),
  markAdminNotificationRead: vi.fn(),
  deleteAdminNotification: vi.fn(),
}));

const SAMPLE_ROW: ContactNotificationRow = {
  id: 42,
  name: "Ada Lovelace",
  first_name: "Ada",
  last_name: "Lovelace",
  email: "ada@analytical.engine",
  subject: "Engine demo request",
  message: "Hello! We would like to schedule an analytical engine demonstration.",
  is_read: false,
  created_at: "2026-11-02T10:00:00Z",
};

const SAMPLE_PAGE: ContactNotificationPage = {
  items: [SAMPLE_ROW],
  total: 1,
  unread_count: 1,
  page: 1,
  limit: 25,
};

describe("AdminNotificationsPage", () => {
  beforeEach(() => {
    vi.mocked(adminService.fetchAdminNotifications).mockReset();
    vi.mocked(adminService.markAdminNotificationRead).mockReset();
    vi.mocked(adminService.deleteAdminNotification).mockReset();
    vi.mocked(adminService.fetchAdminNotifications).mockResolvedValue(SAMPLE_PAGE);
  });

  it("renders notifications listing with sender, email, subject and unread badge", async () => {
    renderWithProviders(<AdminNotificationsPage />, { path: "/admin/notifications" });

    expect(await screen.findByText("Ada Lovelace")).toBeTruthy();
    expect(screen.getByText("ada@analytical.engine")).toBeTruthy();
    expect(screen.getByText("Engine demo request")).toBeTruthy();
    await waitFor(() => {
      expect(
        screen.getAllByText(/Unread|admin\.notifications\.isUnreadBadge/).length,
      ).toBeGreaterThanOrEqual(1);
    });
  });

  it("opens details modal and automatically marks unread message as read", async () => {
    vi.mocked(adminService.markAdminNotificationRead).mockResolvedValue({
      ...SAMPLE_ROW,
      is_read: true,
    });

    renderWithProviders(<AdminNotificationsPage />, { path: "/admin/notifications" });
    const rowSender = await screen.findByText("Ada Lovelace");
    fireEvent.click(rowSender);

    expect(adminService.markAdminNotificationRead).toHaveBeenCalledWith(42, true);
    expect(await screen.findByText(/Reply via email|admin\.notifications\.replyTo/)).toBeTruthy();
    expect(screen.getAllByText(SAMPLE_ROW.message).length).toBeGreaterThanOrEqual(1);
  });

  it("toggles read status manually", async () => {
    vi.mocked(adminService.markAdminNotificationRead).mockResolvedValue({
      ...SAMPLE_ROW,
      is_read: true,
    });

    renderWithProviders(<AdminNotificationsPage />, { path: "/admin/notifications" });
    await screen.findByText("Ada Lovelace");

    const markReadBtn = await screen.findByTitle(
      /Mark as read|admin\.notifications\.markAsRead/,
    );
    fireEvent.click(markReadBtn);

    expect(adminService.markAdminNotificationRead).toHaveBeenCalledWith(42, true);
  });

  it("shows confirm dialog on delete and calls delete API", async () => {
    vi.mocked(adminService.deleteAdminNotification).mockResolvedValue();

    renderWithProviders(<AdminNotificationsPage />, { path: "/admin/notifications" });
    await screen.findByText("Ada Lovelace");

    const deleteBtn = await screen.findByTitle(/Delete|common\.delete/);
    fireEvent.click(deleteBtn);

    expect(await screen.findByText(/Delete inquiry|admin\.notifications\.deleteTitle/)).toBeTruthy();
    const deleteButtons = screen.getAllByRole("button", { name: /Delete|common\.delete/ });
    const confirmBtn = deleteButtons[deleteButtons.length - 1];
    fireEvent.click(confirmBtn);

    await waitFor(() => {
      expect(adminService.deleteAdminNotification).toHaveBeenCalledWith(42);
    });
  });
});
