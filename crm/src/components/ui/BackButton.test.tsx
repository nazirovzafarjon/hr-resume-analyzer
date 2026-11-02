import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import BackButton from "./BackButton";
import { renderWithProviders, LocationProbe } from "../../test/utils";
import { LanguageProvider } from "../../contexts/LanguageContext";

describe("BackButton", () => {
  const originalState = window.history.state;
  const originalConfirm = window.confirm;

  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => {
    Object.defineProperty(window.history, "state", {
      value: originalState,
      configurable: true,
      writable: true,
    });
    window.confirm = originalConfirm;
  });

  it("renders with explicit type='button' to prevent unintended form submissions", () => {
    renderWithProviders(<BackButton fallbackPath="/jobs" label="Back to Jobs" />);
    const btn = screen.getByRole("button", { name: "Back to Jobs" });
    expect(btn.getAttribute("type")).toBe("button");
  });

  it("routes to fallbackPath when history stack is empty (idx === 0)", () => {
    Object.defineProperty(window.history, "state", {
      value: { idx: 0 },
      configurable: true,
      writable: true,
    });

    renderWithProviders(
      <BackButton fallbackPath="/jobs" label="Back" />,
      {
        path: "/jobs/123",
        routes: [{ path: "/jobs", element: <div data-testid="jobs-page">Jobs List</div> }],
      },
    );

    const btn = screen.getByRole("button", { name: "Back" });
    fireEvent.click(btn);

    expect(screen.getByTestId("jobs-page")).toBeTruthy();
  });

  it("navigates back via navigate(-1) when session history exists (idx > 0)", () => {
    Object.defineProperty(window.history, "state", {
      value: { idx: 1 },
      configurable: true,
      writable: true,
    });

    // Render with multiple history entries in MemoryRouter
    render(
      <MemoryRouter initialEntries={["/applications", "/applications/42"]}>
        <LanguageProvider>
          <Routes>
            <Route path="/applications" element={<div data-testid="applications-page">Applications List</div>} />
            <Route
              path="/applications/42"
              element={<BackButton fallbackPath="/fallback-never-reached" label="Back to List" />}
            />
          </Routes>
        </LanguageProvider>
      </MemoryRouter>,
    );

    const btn = screen.getByRole("button", { name: "Back to List" });
    fireEvent.click(btn);

    // Navigates back to /applications
    expect(screen.getByTestId("applications-page")).toBeTruthy();
    expect(screen.queryByText("fallback-never-reached")).toBeNull();
  });

  it("blocks navigation when isDirty is true and user cancels confirmation prompt", () => {
    Object.defineProperty(window.history, "state", {
      value: { idx: 0 },
      configurable: true,
      writable: true,
    });

    const confirmSpy = vi.fn().mockReturnValue(false);
    window.confirm = confirmSpy;

    renderWithProviders(
      <div>
        <BackButton fallbackPath="/jobs" isDirty={true} label="Cancel" />
        <LocationProbe />
      </div>,
      {
        path: "/jobs/create",
        routes: [{ path: "/jobs", element: <div>Jobs</div> }],
      },
    );

    const btn = screen.getByRole("button", { name: "Cancel" });
    fireEvent.click(btn);

    expect(confirmSpy).toHaveBeenCalledTimes(1);
    expect(screen.getByTestId("location").textContent).toBe("/jobs/create");
  });

  it("proceeds with navigation when isDirty is true and user confirms prompt", () => {
    Object.defineProperty(window.history, "state", {
      value: { idx: 0 },
      configurable: true,
      writable: true,
    });

    const confirmSpy = vi.fn().mockReturnValue(true);
    window.confirm = confirmSpy;

    renderWithProviders(
      <BackButton
        fallbackPath="/jobs"
        isDirty={true}
        confirmMessage="Are you sure you want to discard your draft?"
        label="Leave"
      />,
      {
        path: "/jobs/create",
        routes: [{ path: "/jobs", element: <div data-testid="jobs-page">Jobs</div> }],
      },
    );

    const btn = screen.getByRole("button", { name: "Leave" });
    fireEvent.click(btn);

    expect(confirmSpy).toHaveBeenCalledWith("Are you sure you want to discard your draft?");
    expect(screen.getByTestId("jobs-page")).toBeTruthy();
  });

  it("triggers custom onClick callback when provided", () => {
    const onClickSpy = vi.fn();
    renderWithProviders(
      <BackButton fallbackPath="/jobs" onClick={onClickSpy} label="Back" />,
    );

    const btn = screen.getByRole("button", { name: "Back" });
    fireEvent.click(btn);

    expect(onClickSpy).toHaveBeenCalledTimes(1);
  });
});
