import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import ComparativeAnalysis from "./ComparativeAnalysis";
import { LanguageProvider } from "../../contexts/LanguageContext";
import * as applicationsService from "../../services/applicationsService";

vi.mock("../../services/applicationsService", () => ({
  getApplicationComparison: vi.fn(),
}));

function renderWithLang(ui: React.ReactNode, lang: string = "en") {
  localStorage.setItem("resume-analyzer-language", lang);
  return render(<LanguageProvider>{ui}</LanguageProvider>);
}

describe("ComparativeAnalysis", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders requirements fit, relative competitiveness, and disclaimer in English", async () => {
    vi.mocked(applicationsService.getApplicationComparison).mockResolvedValue({
      application_id: 1,
      job_id: 10,
      relative_percentile: 92,
      comparison_pool_size: 15,
      rank: 2,
      has_comparison: true,
      reason: null,
    });

    renderWithLang(
      <ComparativeAnalysis
        applicationId={1}
        jobId={10}
        requirementsFitScore={85}
        isAnalyzed={true}
      />,
      "en",
    );

    await waitFor(() => {
      expect(screen.getByText("Candidate Assessment")).toBeTruthy();
    });

    expect(screen.getByText("Requirements Fit")).toBeTruthy();
    expect(screen.getByText(/85%/)).toBeTruthy();
    expect(screen.getByText("Relative Competitiveness")).toBeTruthy();
    expect(screen.getByText("92")).toBeTruthy();
    expect(screen.getByText("th")).toBeTruthy();
    expect(screen.getByText("Top tier")).toBeTruthy();
    expect(screen.getByText("Rank: 2 of 15")).toBeTruthy();
    expect(screen.getByText("Pool: 15 analyzed")).toBeTruthy();
    expect(screen.getByText("Compared with 15 analyzed candidates for this job")).toBeTruthy();
    expect(screen.getByText("Decision Support Only:")).toBeTruthy();
  });

  it("renders translated strings when active language is Uzbek", async () => {
    vi.mocked(applicationsService.getApplicationComparison).mockResolvedValue({
      application_id: 1,
      job_id: 10,
      relative_percentile: 92,
      comparison_pool_size: 15,
      rank: 2,
      has_comparison: true,
      reason: null,
    });

    renderWithLang(
      <ComparativeAnalysis
        applicationId={1}
        jobId={10}
        requirementsFitScore={85}
        isAnalyzed={true}
      />,
      "uz",
    );

    await waitFor(() => {
      expect(screen.getByText("Nomzodni baholash")).toBeTruthy();
    });

    expect(screen.getByText("Talablarga moslik")).toBeTruthy();
    expect(screen.getByText("Nisbiy raqobatbardoshlik")).toBeTruthy();
    expect(screen.getByText("-o'rin")).toBeTruthy();
    expect(screen.getByText("Yetakchi daraja (Top tier)")).toBeTruthy();
    expect(screen.getByText("O'rin: 15 tadan 2")).toBeTruthy();
    expect(screen.getByText("Hovuz: 15 ta tahlil qilingan")).toBeTruthy();
    expect(screen.getByText("Ushbu ish uchun 15 ta tahlil qilingan nomzod bilan taqqoslandi")).toBeTruthy();
    expect(screen.getByText("Faqat qaror qabul qilishni qo'llab-quvvatlash uchun:")).toBeTruthy();
  });

  it("renders translated strings when active language is Russian", async () => {
    vi.mocked(applicationsService.getApplicationComparison).mockResolvedValue({
      application_id: 1,
      job_id: 10,
      relative_percentile: 92,
      comparison_pool_size: 15,
      rank: 2,
      has_comparison: true,
      reason: null,
    });

    renderWithLang(
      <ComparativeAnalysis
        applicationId={1}
        jobId={10}
        requirementsFitScore={85}
        isAnalyzed={true}
      />,
      "ru",
    );

    await waitFor(() => {
      expect(screen.getByText("Оценка кандидата")).toBeTruthy();
    });

    expect(screen.getByText("Соответствие требованиям")).toBeTruthy();
    expect(screen.getByText("Относительная конкурентоспособность")).toBeTruthy();
    expect(screen.getByText("-й")).toBeTruthy();
    expect(screen.getByText("Высший уровень (Top tier)")).toBeTruthy();
    expect(screen.getByText("Место: 2 из 15")).toBeTruthy();
    expect(screen.getByText("Пул: 15 проанализировано")).toBeTruthy();
    expect(screen.getByText("В сравнении с 15 проанализированными кандидатами на эту вакансию")).toBeTruthy();
    expect(screen.getByText("Исключительно для поддержки решений:")).toBeTruthy();
  });
});
