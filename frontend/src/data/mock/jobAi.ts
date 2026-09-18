import type { JobAIAnalysis } from "../../types/job";

/** Steps shown in the simulated AI processing card. */
export const AI_PROCESSING_STEPS = [
  "Parsing vacancy requirements",
  "Extracting skills & experience signals",
  "Structuring role analysis",
  "Generating application form",
] as const;

/**
 * Deterministic mock AI analysis built from the manual inputs + optional file
 * name. Keeps the Create Job demo believable without any backend.
 */
export function buildMockJobAnalysis(input: {
  position: string;
  company: string;
  description: string;
  skills: string[];
  experience: string;
  fileName?: string;
  instructions?: string;
}): JobAIAnalysis {
  const skills =
    input.skills.length > 0
      ? input.skills
      : ["Communication", "Problem Solving", "Teamwork"];
  const extra = input.fileName
    ? [`Parsed additional context from ${input.fileName}`]
    : [];
  const custom = input.instructions?.trim()
    ? [`Applied custom instruction: "${input.instructions.trim().slice(0, 90)}"`]
    : [];

  return {
    summary:
      `${input.position || "This role"} at ${input.company || "your company"} focuses on ` +
      `${(input.description || "delivering high-quality product outcomes").slice(0, 140)}. ` +
      `Recommended experience: ${input.experience || "2+ years"}.`,
    responsibilities: [
      `Own day-to-day delivery for ${input.position || "the role"}`,
      "Collaborate with product, design and engineering stakeholders",
      "Raise the bar on quality, documentation and code review",
      "Contribute to roadmap planning and continuous improvement",
    ],
    required_skills: skills,
    nice_to_have_skills: ["Docker", "CI/CD", "Agile"],
    experience_level: input.experience || "2+ years",
    seniority_score: input.skills.length >= 4 ? 82 : 68,
    clarity_score: input.description.length > 80 || input.fileName ? 88 : 64,
    completeness_score: input.fileName && input.description ? 91 : 74,
    suggestions: [
      "Add a salary range to increase application conversion.",
      "List 3–5 measurable outcomes for the first 90 days.",
      ...extra,
      ...custom,
    ],
  };
}
