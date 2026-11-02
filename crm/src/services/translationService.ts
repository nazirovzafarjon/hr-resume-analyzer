import { apiRequest } from "./apiClient";

export type TranslatableAnalysisPayload = {
  summary?: string;
  strengths?: string[];
  weaknesses?: string[];
  risks?: string[];
  missing_requirements?: string[];
  matched_requirements?: string[];
  matched_skills?: string[];
  missing_skills?: string[];
  experience_analysis?: string;
  education_analysis?: string;
  relevant_experience?: string[];
  relevant_projects?: string[];
  [key: string]: unknown;
};

export type TranslateAnalysisResponse = {
  target_language: string;
  translated_payload: TranslatableAnalysisPayload;
  cached: boolean;
};

/**
 * Request on-the-fly presentation translation for AI analysis details.
 * Does NOT alter database records.
 */
export async function translateAnalysis(
  targetLanguage: string,
  payload: TranslatableAnalysisPayload,
): Promise<TranslateAnalysisResponse> {
  return apiRequest<TranslateAnalysisResponse>("/translations/translate-analysis", {
    method: "POST",
    body: {
      target_language: targetLanguage,
      payload,
    },
    auth: true,
  });
}
