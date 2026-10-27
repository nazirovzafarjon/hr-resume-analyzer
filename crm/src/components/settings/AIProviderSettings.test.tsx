import { describe, expect, it, vi } from "vitest";
import { screen } from "@testing-library/react";
import AIProviderSettings from "./AIProviderSettings";
import { getAIProvider } from "../../services/settingsService";
import { renderWithProviders } from "../../test/utils";
import type { AIProviderSettings as Status } from "../../types/user";

vi.mock("../../services/settingsService", () => ({
  getAIProvider: vi.fn(),
  saveAIProvider: vi.fn(),
  removeAIProvider: vi.fn(),
  testAIProvider: vi.fn(),
}));

const base: Status = {
  configured: false,
  source: "default",
  provider: null,
  model_id: null,
  masked_api_key: null,
  updated_at: null,
  can_save: true,
  required: false,
  supported_providers: ["openrouter", "groq", "gemini"],
  base_url: null,
};

function renderWith(status: Partial<Status>) {
  vi.mocked(getAIProvider).mockResolvedValueOnce({ ...base, ...status });
  renderWithProviders(<AIProviderSettings />);
}

describe("AIProviderSettings status", () => {
  it("says AI is off until configured when the server requires an own provider", async () => {
    renderWith({ required: true });
    expect(await screen.findByText("Not configured")).toBeTruthy();
    expect(screen.getByText(/run only with your own provider/)).toBeTruthy();
    expect(screen.getByText(/run with your API key and model/)).toBeTruthy();
    expect(screen.queryByText(/default AI provider is used/)).toBeNull();
  });

  it("shows the platform default when a fallback exists", async () => {
    renderWith({ required: false });
    expect(await screen.findByText("Using the default Resume Analyzer AI provider")).toBeTruthy();
    expect(screen.queryByText(/run only with your own provider/)).toBeNull();
    expect(screen.getByText(/default AI provider is used/)).toBeTruthy();
  });

  it("shows the user's own provider without exposing the key", async () => {
    renderWith({
      required: true,
      configured: true,
      source: "custom",
      provider: "openrouter",
      model_id: "deepseek/deepseek-v4.1-flash",
      masked_api_key: "••••••••4f2a",
    });
    expect(await screen.findByText("Using your custom provider")).toBeTruthy();
    expect(screen.queryByText(/run only with your own provider/)).toBeNull();
    const keyInput = document.querySelector('input[type="password"]') as HTMLInputElement;
    expect(keyInput.value).toBe(""); // the saved key is never pre-filled
  });
});
