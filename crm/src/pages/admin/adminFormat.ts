/** Small formatting helpers shared by the admin pages. */

/**
 * Chart axis label for a bucket start date ("2026-09-14" -> "Sep 14").
 * Bucket dates are UTC calendar dates, so they are formatted in UTC to avoid
 * shifting a day in negative-offset time zones.
 */
export function formatShortDate(value: string): string {
  const date = new Date(`${value}T00:00:00Z`);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleDateString("en-US", { month: "short", day: "numeric", timeZone: "UTC" });
}

/** Month axis label ("2026-09-01" -> "Sep 2026"). */
export function formatMonth(value: string): string {
  const date = new Date(`${value}T00:00:00Z`);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleDateString("en-US", { month: "short", year: "numeric", timeZone: "UTC" });
}

/** Milliseconds as a readable duration ("850 ms", "12.4 s"). */
export function formatDuration(ms: number | null | undefined): string {
  if (ms === null || ms === undefined) return "—";
  return ms < 1000 ? `${ms} ms` : `${(ms / 1000).toFixed(1)} s`;
}

/** Parse a positive integer route/query parameter, or null. */
export function parseId(value: string | undefined | null): number | null {
  const parsed = Number.parseInt(value ?? "", 10);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : null;
}
