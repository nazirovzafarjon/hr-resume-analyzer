import { describe, expect, it, vi } from "vitest";
import { fetchAllPages } from "./pagination";

const rows = (from: number, count: number) =>
  Array.from({ length: count }, (_, index) => ({ id: from + index }));

describe("fetchAllPages", () => {
  it("keeps reading until a short page comes back", async () => {
    const fetchPage = vi
      .fn()
      .mockResolvedValueOnce(rows(1, 2))
      .mockResolvedValueOnce(rows(3, 2))
      .mockResolvedValueOnce(rows(5, 1));

    const result = await fetchAllPages(fetchPage, 2);

    expect(result.map((row) => row.id)).toEqual([1, 2, 3, 4, 5]);
    expect(fetchPage.mock.calls).toEqual([
      [0, 2],
      [2, 2],
      [4, 2],
    ]);
  });

  it("stops after an empty page when the total is a multiple of the page size", async () => {
    const fetchPage = vi.fn().mockResolvedValueOnce(rows(1, 2)).mockResolvedValueOnce([]);
    expect(await fetchAllPages(fetchPage, 2)).toHaveLength(2);
    expect(fetchPage).toHaveBeenCalledTimes(2);
  });

  it("drops a row repeated because a new record shifted the offsets", async () => {
    const fetchPage = vi
      .fn()
      .mockResolvedValueOnce(rows(1, 2))
      .mockResolvedValueOnce([{ id: 2 }, { id: 3 }])
      .mockResolvedValueOnce([]);
    expect((await fetchAllPages(fetchPage, 2)).map((row) => row.id)).toEqual([1, 2, 3]);
  });

  it("never loops past maxPages", async () => {
    const fetchPage = vi.fn(async (skip: number) => rows(skip + 1, 2));
    expect(await fetchAllPages(fetchPage, 2, 3)).toHaveLength(6);
    expect(fetchPage).toHaveBeenCalledTimes(3);
  });
});
