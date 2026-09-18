import type { JobInput } from "../types/job";

export type CategoryBreakdown = {
  category: string;
  jobs: number;
  candidates: number;
};

export type AnalyticsGroupBy = "company" | "position" | "experience";

function categoryKey(job: JobInput, groupBy: AnalyticsGroupBy): string {
  switch (groupBy) {
    case "company":
      return job.company_name;
    case "position":
      return job.position;
    case "experience":
    default:
      return job.required_experience || "Not specified";
  }
}

/**
 * Build the categories + candidate counts shown in the dashboard analytics
 * chart, grouping jobs by the chosen dimension. This mirrors what the backend
 * `/api/dashboard/overview?category=...` endpoint will return later.
 */
export function buildAnalytics(
  jobs: JobInput[],
  groupBy: AnalyticsGroupBy,
): CategoryBreakdown[] {
  const buckets = new Map<string, { jobs: number; candidates: number }>();

  for (const job of jobs) {
    const key = categoryKey(job, groupBy);
    const bucket = buckets.get(key) ?? { jobs: 0, candidates: 0 };
    bucket.jobs += 1;
    bucket.candidates += job.leads_count;
    buckets.set(key, bucket);
  }

  return Array.from(buckets.entries())
    .map(([category, { jobs, candidates }]) => ({
      category,
      jobs,
      candidates,
    }))
    .sort((a, b) => b.candidates - a.candidates || a.category.localeCompare(b.category));
}