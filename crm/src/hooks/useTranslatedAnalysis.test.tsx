import { describe, expect, it, vi, beforeEach } from "vitest";
import { renderHook, waitFor, act } from "@testing-library/react";
import type { ReactNode } from "react";
import { LanguageProvider, useLanguage } from "../contexts/LanguageContext";
import { useTranslatedAnalysis, detectSourceLanguage } from "./useTranslatedAnalysis";
import { translateAnalysis } from "../services/translationService";
import type { ApplicationAnalysis } from "../types/candidate";

vi.mock("../services/translationService", () => ({
  translateAnalysis: vi.fn(),
}));

const mockAnalysis: ApplicationAnalysis = {
  match_percentage: 88,
  summary: "Experienced software engineer with expertise in React and TypeScript.",
  matched_requirements: ["React experience", "TypeScript knowledge"],
  missing_requirements: ["GraphQL knowledge"],
  matched_skills: ["React", "TypeScript", "Node.js"],
  missing_skills: ["GraphQL"],
  strengths: ["Strong problem-solving ability", "Excellent communicator"],
  weaknesses: ["No experience with GraphQL"],
  risks: [],
  experience_analysis: "Over 4 years building scalable SPAs.",
  education_analysis: "B.S. in Computer Science.",
  relevant_experience: ["Frontend Lead at TechCorp"],
  relevant_projects: ["Internal CRM rewrite"],
  ai_recommendation: "hire",
};

const translatedUzPayload = {
  summary: "React va TypeScript bo'yicha tajribaga ega dasturiy ta'minot muhandisi.",
  strengths: ["Kuchli muammolarni hal qilish qobiliyati"],
  weaknesses: ["GraphQL bilan tajriba yo'q"],
  risks: [],
  missing_requirements: ["GraphQL bilimi"],
  matched_requirements: ["React tajribasi", "TypeScript bilimi"],
  matched_skills: ["React", "TypeScript"],
  missing_skills: ["GraphQL"],
  experience_analysis: "Kengaytiriladigan SPAlar yaratish bo'yicha 4 yildan ortiq tajriba.",
  education_analysis: "Kompyuter fanlari bo'yicha bakalavr.",
  relevant_experience: ["TechCorp kompaniyasida Frontend yetakchisi"],
  relevant_projects: ["Ichki CRM qayta yozilishi"],
};

function wrapper({ children }: { children: ReactNode }) {
  return <LanguageProvider>{children}</LanguageProvider>;
}

describe("useTranslatedAnalysis", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    sessionStorage.clear();
    localStorage.clear();
  });

  describe("detectSourceLanguage", () => {
    it("detects English from Latin text without Uzbek markers", () => {
      expect(detectSourceLanguage("Senior Python Developer with 5 years experience")).toBe("en");
    });

    it("detects Uzbek Latin from text containing Uzbek words or apostrophes", () => {
      expect(detectSourceLanguage("Malakali mutaxassis bo'yicha talablar va tajriba")).toBe("uz");
    });

    it("detects Russian from standard Cyrillic text", () => {
      expect(detectSourceLanguage("Опытный разработчик программного обеспечения")).toBe("ru");
    });

    it("detects Uzbek Cyrillic from text with specific letters like ў or қ", () => {
      expect(detectSourceLanguage("Малакали мутахассис бўйича талаблар")).toBe("kiril");
    });
  });

  it("returns original analysis immediately if target language matches source language", () => {
    // Default language is 'en' and mockAnalysis is in English
    const { result } = renderHook(
      () => useTranslatedAnalysis(mockAnalysis, 123),
      { wrapper },
    );

    expect(result.current.isOriginal).toBe(true);
    expect(result.current.isTranslating).toBe(false);
    expect(result.current.translatedAnalysis?.summary).toBe(mockAnalysis.summary);
    expect(translateAnalysis).not.toHaveBeenCalled();
  });

  it("handles null or undefined rawAnalysis cleanly", () => {
    const { result } = renderHook(
      () => useTranslatedAnalysis(null, 123),
      { wrapper },
    );

    expect(result.current.translatedAnalysis).toBeNull();
    expect(result.current.isTranslating).toBe(false);
    expect(translateAnalysis).not.toHaveBeenCalled();
  });

  it("triggers translation and merges translated text when language is changed", async () => {
    vi.mocked(translateAnalysis).mockResolvedValueOnce({
      target_language: "uz",
      translated_payload: translatedUzPayload,
      cached: false,
    });

    const { result } = renderHook(
      () => {
        const langCtx = useLanguage();
        const trans = useTranslatedAnalysis(mockAnalysis, 123);
        return { langCtx, trans };
      },
      { wrapper },
    );

    // Switch language to Uzbek
    act(() => {
      result.current.langCtx.setLanguage("uz");
    });

    await waitFor(() => {
      expect(translateAnalysis).toHaveBeenCalledWith("uz", expect.any(Object));
    });

    await waitFor(() => {
      expect(result.current.trans.isTranslating).toBe(false);
    });

    expect(result.current.trans.translatedAnalysis?.summary).toBe(translatedUzPayload.summary);
    expect(result.current.trans.translatedAnalysis?.match_percentage).toBe(88); // Metadata preserved!
    expect(result.current.trans.isOriginal).toBe(false);

    // Check that sessionStorage cache was populated
    const cached = sessionStorage.getItem("analysis_trans_123_uz");
    expect(cached).toBeTruthy();
    expect(JSON.parse(cached!).summary).toBe(translatedUzPayload.summary);
  });

  it("falls back to original analysis on translation API error", async () => {
    vi.mocked(translateAnalysis).mockRejectedValueOnce(new Error("Network timeout"));

    const { result } = renderHook(
      () => {
        const langCtx = useLanguage();
        const trans = useTranslatedAnalysis(mockAnalysis, 456);
        return { langCtx, trans };
      },
      { wrapper },
    );

    act(() => {
      result.current.langCtx.setLanguage("ru");
    });

    await waitFor(() => {
      expect(result.current.trans.isTranslating).toBe(false);
    });

    expect(result.current.trans.isFallback).toBe(true);
    expect(result.current.trans.translatedAnalysis?.summary).toBe(mockAnalysis.summary);
    expect(result.current.trans.error).toBe("Network timeout");
  });
});
