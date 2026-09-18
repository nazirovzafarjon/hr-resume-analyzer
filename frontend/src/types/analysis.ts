/** Resume analysis types. Field names mirror the backend `app/schemas/analysis.py`. */

export type SkillMatch = {
  skill: string;
  found: boolean;
};

export type ResumeAnalysis = {
  score: number;
  matched_skills: string[];
  missing_skills: string[];
  skill_matches: SkillMatch[];
  summary: string;
};