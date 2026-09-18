import type { ResumeAnalysis } from "../../types/analysis";

/**
 * Static demo resume analyses keyed by candidate id. The shape matches the
 * backend `AnalysisResult`, so wiring in the real endpoint later only requires
 * replacing this map look-up with an API call.
 */
export const mockAnalysis: Record<number, ResumeAnalysis> = {
  1: {
    score: 87,
    matched_skills: ["Python", "FastAPI", "PostgreSQL", "REST API"],
    missing_skills: ["Docker"],
    skill_matches: [
      { skill: "Python", found: true },
      { skill: "FastAPI", found: true },
      { skill: "PostgreSQL", found: true },
      { skill: "REST API", found: true },
      { skill: "Docker", found: false },
    ],
    summary:
      "Strong alignment with the role. Deep Python and FastAPI experience, " +
      "with production API work and solid PostgreSQL skills.",
  },
  2: {
    score: 72,
    matched_skills: ["Python", "PostgreSQL"],
    missing_skills: ["FastAPI", "REST API", "Docker"],
    skill_matches: [
      { skill: "Python", found: true },
      { skill: "PostgreSQL", found: true },
      { skill: "FastAPI", found: false },
      { skill: "REST API", found: false },
      { skill: "Docker", found: false },
    ],
    summary:
      "Solid Python foundation but limited exposure to FastAPI and modern " +
      "API patterns. Would need ramp-up.",
  },
  3: {
    score: 78,
    matched_skills: ["Python", "REST API", "Docker"],
    missing_skills: ["FastAPI", "PostgreSQL"],
    skill_matches: [
      { skill: "Python", found: true },
      { skill: "REST API", found: true },
      { skill: "Docker", found: true },
      { skill: "FastAPI", found: false },
      { skill: "PostgreSQL", found: false },
    ],
    summary:
      "Good all-round backend experience with a strong grasp of REST. " +
      "StrongInterviewFastAPI and PostgreSQL familiarity is thinner.",
  },
  4: {
    score: 90,
    matched_skills: ["React", "TypeScript", "JavaScript"],
    missing_skills: [],
    skill_matches: [
      { skill: "React", found: true },
      { skill: "TypeScript", found: true },
      { skill: "JavaScript", found: true },
    ],
    summary:
      "Excellent frontend profile covering all required skills, with strong " +
      "React and TypeScript production experience.",
  },
  5: {
    score: 61,
    matched_skills: ["TypeScript"],
    missing_skills: ["React", "JavaScript"],
    skill_matches: [
      { skill: "TypeScript", found: true },
      { skill: "React", found: false },
      { skill: "JavaScript", found: false },
    ],
    summary:
      "Comfortable with TypeScript but little hands-on React experience. " +
      "Probably a mid-level conversion candidate.",
  },
  6: {
    score: 82,
    matched_skills: ["Docker", "AWS", "CI/CD", "Kubernetes"],
    missing_skills: [],
    skill_matches: [
      { skill: "Docker", found: true },
      { skill: "Kubernetes", found: true },
      { skill: "AWS", found: true },
      { skill: "CI/CD", found: true },
    ],
    summary:
      "Strong DevOps track record covering containers, orchestration and " +
      "cloud delivery end to end.",
  },
  7: {
    score: 44,
    matched_skills: ["Docker"],
    missing_skills: ["Kubernetes", "AWS", "CI/CD"],
    skill_matches: [
      { skill: "Docker", found: true },
      { skill: "Kubernetes", found: false },
      { skill: "AWS", found: false },
      { skill: "CI/CD", found: false },
    ],
    summary:
      "Early-stage DevOps exposure. Several core requirements are missing, so " +
      "the fit for a senior role is limited.",
  },
  8: {
    score: 69,
    matched_skills: ["Agile", "Roadmapping"],
    missing_skills: ["Product Strategy"],
    skill_matches: [
      { skill: "Product Strategy", found: false },
      { skill: "Agile", found: true },
      { skill: "Roadmapping", found: true },
    ],
    summary:
      "Practical delivery and roadmapping skills, with lighter strategy " +
      "depth. A reasonable, coachable candidate.",
  },
  9: {
    score: 85,
    matched_skills: ["SQL", "Python", "Pandas", "Tableau"],
    missing_skills: [],
    skill_matches: [
      { skill: "SQL", found: true },
      { skill: "Python", found: true },
      { skill: "Pandas", found: true },
      { skill: "Tableau", found: true },
    ],
    summary:
      "Complete coverage of the required data stack with strong hands-on " +
      "reporting experience.",
  },
  10: {
    score: 76,
    matched_skills: ["Python", "Testing"],
    missing_skills: ["Selenium"],
    skill_matches: [
      { skill: "Selenium", found: false },
      { skill: "Python", found: true },
      { skill: "Testing", found: true },
    ],
    summary:
      "Good testing mindset and Python skills; would add Selenium-specific " +
      "automation knowledge quickly.",
  },
};

/** Fallback used for candidates without an explicit analysis entry. */
export const defaultAnalysis: ResumeAnalysis = {
  score: 60,
  matched_skills: [],
  missing_skills: [],
  skill_matches: [],
  summary: "Analysis pending for this candidate.",
};

export function getMockAnalysis(candidateId: number): ResumeAnalysis {
  return mockAnalysis[candidateId] ?? defaultAnalysis;
}