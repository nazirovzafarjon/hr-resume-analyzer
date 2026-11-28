import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, screen, waitFor } from "@testing-library/react";
import HelpWidget from "./HelpWidget";
import { renderWithProviders } from "../../test/utils";
import type { SupportConversation } from "../../types/support";

vi.mock("../../hooks/useSupportStream", () => ({ useSupportStream: () => ({ connected: true }) }));
vi.mock("../../services/supportService", () => ({
  supportBase: (session: string) => (session === "candidate" ? "/candidate/support" : "/support"),
  fetchMySupportUnreadCount: vi.fn(),
  fetchMySupportConversations: vi.fn(),
  fetchMySupportConversation: vi.fn(),
  openSupportConversation: vi.fn(),
  sendSupportMessage: vi.fn(),
}));

import {
  fetchMySupportConversation,
  fetchMySupportConversations,
  fetchMySupportUnreadCount,
  openSupportConversation,
  sendSupportMessage,
} from "../../services/supportService";

const NOW = "2026-11-28T10:00:00Z";

function conversation(overrides: Partial<SupportConversation> = {}): SupportConversation {
  return {
    id: 7,
    status: "open",
    created_at: NOW,
    last_message_at: NOW,
    closed_at: null,
    unread_count: 0,
    messages: [
      { id: 1, sender: "requester", author_name: null, body: "Export is broken", created_at: NOW },
      { id: 2, sender: "admin", author_name: "Aziza", body: "Looking into it", created_at: NOW },
    ],
    ...overrides,
  };
}

describe("HelpWidget", () => {
  beforeEach(() => {
    vi.mocked(fetchMySupportUnreadCount).mockReset().mockResolvedValue({ unread_count: 0 });
    vi.mocked(fetchMySupportConversations).mockReset();
    vi.mocked(fetchMySupportConversation).mockReset();
    vi.mocked(openSupportConversation).mockReset();
    vi.mocked(sendSupportMessage).mockReset();
  });

  it("shows the unread badge on the Help button", async () => {
    vi.mocked(fetchMySupportUnreadCount).mockResolvedValue({ unread_count: 2 });
    renderWithProviders(<HelpWidget session="hr" />);
    expect(await screen.findByRole("button", { name: "Help (2)" })).toBeTruthy();
  });

  it("starts a first conversation with the current page attached", async () => {
    vi.mocked(fetchMySupportConversations).mockResolvedValue([]);
    vi.mocked(openSupportConversation).mockResolvedValue(
      conversation({ messages: [{ id: 1, sender: "requester", author_name: null, body: "Hi", created_at: NOW }] }),
    );
    renderWithProviders(<HelpWidget session="candidate" />, { path: "/candidate/profile" });

    fireEvent.click(await screen.findByRole("button", { name: "Help" }));
    const box = await screen.findByPlaceholderText("Describe your problem…");
    fireEvent.change(box, { target: { value: "  Hi  " } });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));

    await waitFor(() =>
      expect(openSupportConversation).toHaveBeenCalledWith("candidate", "Hi", "/candidate/profile"),
    );
    expect(await screen.findByText("Thanks! The support team will reply here soon.")).toBeTruthy();
  });

  it("shows the latest conversation and lets the requester reply", async () => {
    vi.mocked(fetchMySupportConversations).mockResolvedValue([conversation()]);
    vi.mocked(fetchMySupportConversation).mockResolvedValue(conversation());
    vi.mocked(sendSupportMessage).mockResolvedValue(conversation());
    renderWithProviders(<HelpWidget session="hr" />);

    fireEvent.click(await screen.findByRole("button", { name: "Help" }));
    expect(await screen.findByText("Looking into it")).toBeTruthy();
    expect(screen.getByText("Aziza · Support")).toBeTruthy();

    const box = screen.getByPlaceholderText("Write a message…");
    fireEvent.change(box, { target: { value: "Thanks" } });
    fireEvent.keyDown(box, { key: "Enter" });
    await waitFor(() => expect(sendSupportMessage).toHaveBeenCalledWith("hr", 7, "Thanks"));
  });

  it("keeps a closed conversation read-only and offers a new one", async () => {
    const closed = conversation({ status: "closed", closed_at: NOW });
    vi.mocked(fetchMySupportConversations).mockResolvedValue([closed]);
    vi.mocked(fetchMySupportConversation).mockResolvedValue(closed);
    renderWithProviders(<HelpWidget session="hr" />);

    fireEvent.click(await screen.findByRole("button", { name: "Help" }));
    expect(await screen.findByText("Support closed this conversation.")).toBeTruthy();
    expect(screen.queryByPlaceholderText("Write a message…")).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "Start a new conversation" }));
    expect(await screen.findByPlaceholderText("Describe your problem…")).toBeTruthy();
  });
});
