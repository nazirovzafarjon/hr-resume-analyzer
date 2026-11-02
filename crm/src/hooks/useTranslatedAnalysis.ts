import { useEffect, useState, useMemo } from "react";
import { useLanguage, type Language } from "../contexts/LanguageContext";
import type { ApplicationAnalysis } from "../types/candidate";
import {
  translateAnalysis,
  type TranslatableAnalysisPayload,
} from "../services/translationService";

// In-memory module-level cache to avoid repeated JSON.parse or storage access
const memoryCache = new Map<string, ApplicationAnalysis>();

/**
 * Heuristically detect whether the source text is written in uz, kiril, ru, or en.
 */
export function detectSourceLanguage(text: string): Language {
  if (!text || !text.trim()) return "en";

  // Uzbek Cyrillic specific letters (ў, қ, ғ, ҳ)
  if (/[ўқғҳЎҚҒҲ]/.test(text)) {
    return "kiril";
  }

  // General Cyrillic characters -> Russian
  if (/[а-яА-ЯёЁ]/.test(text)) {
    return "ru";
  }

  // Uzbek Latin markers
  if (
    /\b(va|uchun|bilan|tajriba|malaka|bo['`ʻ]yicha|talablar|ko['`ʻ]nikmalar|yillik|darajasi)\b/i.test(
      text,
    ) ||
    /[og]['`ʻ]/i.test(text)
  ) {
    return "uz";
  }

  // Default assumption for Latin text
  return "en";
}

/**
 * Extracts translatable narrative fields from the analysis payload.
 */
function extractTranslatablePayload(
  analysis: ApplicationAnalysis,
): TranslatableAnalysisPayload {
  return {
    summary: analysis.summary || "",
    strengths: analysis.strengths || [],
    weaknesses: analysis.weaknesses || [],
    risks: analysis.risks || [],
    missing_requirements: analysis.missing_requirements || [],
    matched_requirements: analysis.matched_requirements || [],
    matched_skills: analysis.matched_skills || [],
    missing_skills: analysis.missing_skills || [],
    experience_analysis: analysis.experience_analysis || "",
    education_analysis: analysis.education_analysis || "",
    relevant_experience: analysis.relevant_experience || [],
    relevant_projects: analysis.relevant_projects || [],
  };
}

/**
 * Merges translated narrative text back with untouched metadata/numbers.
 */
function mergeTranslatedAnalysis(
  original: ApplicationAnalysis,
  translated: TranslatableAnalysisPayload,
): ApplicationAnalysis {
  return {
    ...original,
    summary: typeof translated.summary === "string" ? translated.summary : original.summary,
    strengths: Array.isArray(translated.strengths)
      ? (translated.strengths as string[])
      : original.strengths,
    weaknesses: Array.isArray(translated.weaknesses)
      ? (translated.weaknesses as string[])
      : original.weaknesses,
    risks: Array.isArray(translated.risks)
      ? (translated.risks as string[])
      : original.risks,
    missing_requirements: Array.isArray(translated.missing_requirements)
      ? (translated.missing_requirements as string[])
      : original.missing_requirements,
    matched_requirements: Array.isArray(translated.matched_requirements)
      ? (translated.matched_requirements as string[])
      : original.matched_requirements,
    matched_skills: Array.isArray(translated.matched_skills)
      ? (translated.matched_skills as string[])
      : original.matched_skills,
    missing_skills: Array.isArray(translated.missing_skills)
      ? (translated.missing_skills as string[])
      : original.missing_skills,
    experience_analysis:
      typeof translated.experience_analysis === "string"
        ? translated.experience_analysis
        : original.experience_analysis,
    education_analysis:
      typeof translated.education_analysis === "string"
        ? translated.education_analysis
        : original.education_analysis,
    relevant_experience: Array.isArray(translated.relevant_experience)
      ? (translated.relevant_experience as string[])
      : original.relevant_experience,
    relevant_projects: Array.isArray(translated.relevant_projects)
      ? (translated.relevant_projects as string[])
      : original.relevant_projects,
  };
}

export type UseTranslatedAnalysisResult = {
  translatedAnalysis: ApplicationAnalysis | null | undefined;
  isTranslating: boolean;
  isOriginal: boolean;
  isFallback: boolean;
  error: string | null;
  targetLanguage: Language;
};

/**
 * Reusable React hook for on-the-fly dynamic AI analysis translation.
 *
 * Guarantees:
 * - Read-only view translation (never mutates or posts back to PostgreSQL).
 * - Multi-tier caching in memory and sessionStorage.
 * - Graceful fallback to original text on translation timeout or failure.
 */
export function useTranslatedAnalysis(
  rawAnalysis: ApplicationAnalysis | null | undefined,
  applicationId?: number | string,
  options?: { enabled?: boolean },
): UseTranslatedAnalysisResult {
  const { language } = useLanguage();
  const enabled = options?.enabled ?? true;

  // Extract combined representative text to detect source language
  const combinedSample = useMemo(() => {
    if (!rawAnalysis) return "";
    return [
      rawAnalysis.summary,
      ...(rawAnalysis.strengths || []),
      ...(rawAnalysis.matched_requirements || []),
      rawAnalysis.experience_analysis,
    ]
      .filter(Boolean)
      .join(" ");
  }, [rawAnalysis]);

  const sourceLanguage = useMemo(
    () => detectSourceLanguage(combinedSample),
    [combinedSample],
  );

  const isSameLanguage = sourceLanguage === language;

  // Compute a deterministic cache key
  const cacheKey = useMemo(() => {
    const id = applicationId ?? "anon";
    return `analysis_trans_${id}_${language}`;
  }, [applicationId, language]);

  const [translatedState, setTranslatedState] = useState<{
    key: string;
    analysis: ApplicationAnalysis | null | undefined;
    isTranslating: boolean;
    isOriginal: boolean;
    isFallback: boolean;
    error: string | null;
  }>(() => {
    if (!rawAnalysis || !enabled || isSameLanguage) {
      return {
        key: cacheKey,
        analysis: rawAnalysis,
        isTranslating: false,
        isOriginal: true,
        isFallback: false,
        error: null,
      };
    }
    // Check in-memory cache
    if (memoryCache.has(cacheKey)) {
      return {
        key: cacheKey,
        analysis: memoryCache.get(cacheKey),
        isTranslating: false,
        isOriginal: false,
        isFallback: false,
        error: null,
      };
    }
    // Check sessionStorage cache
    if (typeof window !== "undefined") {
      try {
        const stored = sessionStorage.getItem(cacheKey);
        if (stored) {
          const parsed = JSON.parse(stored) as ApplicationAnalysis;
          memoryCache.set(cacheKey, parsed);
          return {
            key: cacheKey,
            analysis: parsed,
            isTranslating: false,
            isOriginal: false,
            isFallback: false,
            error: null,
          };
        }
      } catch {
        /* ignore storage error */
      }
    }
    return {
      key: cacheKey,
      analysis: rawAnalysis,
      isTranslating: true,
      isOriginal: false,
      isFallback: false,
      error: null,
    };
  });

  useEffect(() => {
    if (!rawAnalysis || !enabled) {
      setTranslatedState({
        key: cacheKey,
        analysis: rawAnalysis,
        isTranslating: false,
        isOriginal: true,
        isFallback: false,
        error: null,
      });
      return;
    }

    // If active language matches original source language, skip translation
    if (isSameLanguage) {
      setTranslatedState({
        key: cacheKey,
        analysis: rawAnalysis,
        isTranslating: false,
        isOriginal: true,
        isFallback: false,
        error: null,
      });
      return;
    }

    // 1. Check memory cache
    if (memoryCache.has(cacheKey)) {
      setTranslatedState({
        key: cacheKey,
        analysis: memoryCache.get(cacheKey),
        isTranslating: false,
        isOriginal: false,
        isFallback: false,
        error: null,
      });
      return;
    }

    // 2. Check sessionStorage
    if (typeof window !== "undefined") {
      try {
        const stored = sessionStorage.getItem(cacheKey);
        if (stored) {
          const parsed = JSON.parse(stored) as ApplicationAnalysis;
          memoryCache.set(cacheKey, parsed);
          setTranslatedState({
            key: cacheKey,
            analysis: parsed,
            isTranslating: false,
            isOriginal: false,
            isFallback: false,
            error: null,
          });
          return;
        }
      } catch {
        /* storage access fallback */
      }
    }

    // 3. Trigger remote translation
    let cancelled = false;
    setTranslatedState((prev) => ({
      ...prev,
      key: cacheKey,
      isTranslating: true,
      error: null,
      isFallback: false,
    }));

    const payload = extractTranslatablePayload(rawAnalysis);

    translateAnalysis(language, payload)
      .then((res) => {
        if (cancelled) return;
        const merged = mergeTranslatedAnalysis(rawAnalysis, res.translated_payload);
        memoryCache.set(cacheKey, merged);
        try {
          if (typeof window !== "undefined") {
            sessionStorage.setItem(cacheKey, JSON.stringify(merged));
          }
        } catch {
          /* ignore quota or privacy errors */
        }
        setTranslatedState({
          key: cacheKey,
          analysis: merged,
          isTranslating: false,
          isOriginal: false,
          isFallback: false,
          error: null,
        });
      })
      .catch((err) => {
        if (cancelled) return;
        const msg = err instanceof Error ? err.message : "Translation unavailable";
        // Graceful fallback: return original analysis with error flag
        setTranslatedState({
          key: cacheKey,
          analysis: rawAnalysis,
          isTranslating: false,
          isOriginal: true,
          isFallback: true,
          error: msg,
        });
      });

    return () => {
      cancelled = true;
    };
  }, [rawAnalysis, cacheKey, language, isSameLanguage, enabled]);

  // If state is for an older key, display fallback smoothly while effect updates
  const effectiveAnalysis =
    translatedState.key === cacheKey ? translatedState.analysis : rawAnalysis;
  const isTranslating =
    translatedState.key === cacheKey
      ? translatedState.isTranslating
      : Boolean(rawAnalysis) && !isSameLanguage && !memoryCache.has(cacheKey);

  return {
    translatedAnalysis: effectiveAnalysis,
    isTranslating,
    isOriginal: isSameLanguage || translatedState.isOriginal,
    isFallback: translatedState.isFallback,
    error: translatedState.error,
    targetLanguage: language,
  };
}
