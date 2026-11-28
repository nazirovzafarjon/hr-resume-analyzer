import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, renderHook } from "@testing-library/react";
import { useDeadlinePassed } from "./useDeadlinePassed";

describe("useDeadlinePassed", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-12-01T10:00:00Z"));
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  it("is false without a deadline", () => {
    const { result } = renderHook(() => useDeadlinePassed(null));
    expect(result.current).toBe(false);
  });

  it("is true at once for a deadline already in the past", () => {
    const { result } = renderHook(() => useDeadlinePassed(Date.now() - 1));
    expect(result.current).toBe(true);
  });

  it("flips exactly when the deadline passes", () => {
    const deadline = Date.now() + 5_000;
    const { result } = renderHook(() => useDeadlinePassed(deadline));
    expect(result.current).toBe(false);

    act(() => {
      vi.advanceTimersByTime(4_999);
    });
    expect(result.current).toBe(false);

    act(() => {
      vi.advanceTimersByTime(1);
    });
    expect(result.current).toBe(true);
  });

  it("starts over for a new deadline", () => {
    const { result, rerender } = renderHook(({ deadline }) => useDeadlinePassed(deadline), {
      initialProps: { deadline: Date.now() + 1_000 },
    });
    act(() => {
      vi.advanceTimersByTime(1_000);
    });
    expect(result.current).toBe(true);

    rerender({ deadline: Date.now() + 2_000 });
    expect(result.current).toBe(false);
    act(() => {
      vi.advanceTimersByTime(2_000);
    });
    expect(result.current).toBe(true);
  });

  it("clears its timer on unmount", () => {
    const { unmount } = renderHook(() => useDeadlinePassed(Date.now() + 1_000));
    expect(vi.getTimerCount()).toBe(1);
    unmount();
    expect(vi.getTimerCount()).toBe(0);
  });
});
