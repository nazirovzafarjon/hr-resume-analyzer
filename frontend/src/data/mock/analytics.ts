import type {
  HiringFunnelStage,
  ScoreBucket,
  WeeklyVolume,
} from "../../types/application";

/** Lightweight mock analytics — rendered with pure CSS bars (no chart lib). */
export const mockFunnel: HiringFunnelStage[] = [
  { stage: "Applied", count: 10 },
  { stage: "Screening", count: 7 },
  { stage: "Interview", count: 4 },
  { stage: "Shortlisted", count: 3 },
  { stage: "Hired", count: 1 },
];

export const mockScoreBuckets: ScoreBucket[] = [
  { bucket: "0–49", count: 1 },
  { bucket: "50–59", count: 0 },
  { bucket: "60–69", count: 2 },
  { bucket: "70–79", count: 3 },
  { bucket: "80–89", count: 3 },
  { bucket: "90–100", count: 1 },
];

export const mockWeeklyVolume: WeeklyVolume[] = [
  { week: "Jul 28", applications: 1, interviews: 0 },
  { week: "Aug 4", applications: 1, interviews: 0 },
  { week: "Aug 11", applications: 1, interviews: 1 },
  { week: "Aug 18", applications: 2, interviews: 1 },
  { week: "Aug 25", applications: 2, interviews: 2 },
  { week: "Sep 1", applications: 3, interviews: 1 },
];
