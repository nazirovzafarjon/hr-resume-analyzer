import { describe, expect, it } from "vitest";
import { renderHook } from "@testing-library/react";
import { useEffect } from "react";
import { useLatestRef } from "./useLatestRef";

describe("useLatestRef", () => {
  it("keeps one ref object and holds the latest committed value", () => {
    const { result, rerender } = renderHook(({ value }) => useLatestRef(value), {
      initialProps: { value: "a" },
    });
    const first = result.current;
    expect(first.current).toBe("a");

    rerender({ value: "b" });
    expect(result.current).toBe(first);
    expect(first.current).toBe("b");
  });

  it("is already updated when effects of the same commit run", () => {
    const seen: string[] = [];
    const { rerender } = renderHook(
      ({ value }) => {
        const ref = useLatestRef(value);
        useEffect(() => {
          seen.push(ref.current);
        }, [value, ref]);
      },
      { initialProps: { value: "first" } },
    );
    rerender({ value: "second" });
    expect(seen).toEqual(["first", "second"]);
  });
});
