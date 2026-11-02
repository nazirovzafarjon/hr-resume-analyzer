import { describe, expect, it } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import ApplicationAnswers from "./ApplicationAnswers";
import { LanguageProvider } from "../../contexts/LanguageContext";
import type { ApplicantAnswer } from "../../types/candidate";

function renderWithLang(ui: React.ReactNode, lang: string = "en") {
  localStorage.setItem("resume-analyzer-language", lang);
  return render(<LanguageProvider>{ui}</LanguageProvider>);
}

describe("ApplicationAnswers", () => {
  it("translates standard question labels into the active language", async () => {
    const answers: ApplicantAnswer[] = [
      { field_id: "1", key: "full_name", label: "Full name", type: "text", value: "Ali Valiyev" },
      { field_id: "2", key: "email", label: "Email", type: "email", value: "ali@example.com" },
      { field_id: "3", key: "phone", label: "Phone", type: "phone", value: "+998901234567" },
      { field_id: "4", key: "resume", label: "Resume", type: "file", value: "cv.pdf" },
      { field_id: "5", key: "custom_quest", label: "Favorite Tech Stack", type: "text", value: "React + Python" },
    ];

    // English
    const { unmount } = renderWithLang(<ApplicationAnswers answers={answers} />, "en");
    await waitFor(() => {
      expect(screen.getByText("File attached")).toBeTruthy();
    });
    expect(screen.getByText("Full name")).toBeTruthy();
    expect(screen.getByText("Email")).toBeTruthy();
    expect(screen.getByText("Phone")).toBeTruthy();
    expect(screen.getByText("Resume")).toBeTruthy();
    expect(screen.getByText("Favorite Tech Stack")).toBeTruthy();
    unmount();

    // Uzbek
    const { unmount: unmountUz } = renderWithLang(<ApplicationAnswers answers={answers} />, "uz");
    await waitFor(() => {
      expect(screen.getByText("Fayl biriktirilgan")).toBeTruthy();
    });
    expect(screen.getByText("To'liq ism")).toBeTruthy();
    expect(screen.getByText("Elektron pochta")).toBeTruthy();
    expect(screen.getByText("Telefon raqami")).toBeTruthy();
    expect(screen.getByText("Rezyume")).toBeTruthy();
    expect(screen.getByText("Favorite Tech Stack")).toBeTruthy();
    unmountUz();

    // Russian
    const { unmount: unmountRu } = renderWithLang(<ApplicationAnswers answers={answers} />, "ru");
    await waitFor(() => {
      expect(screen.getByText("Файл прикреплен")).toBeTruthy();
    });
    expect(screen.getByText("Полное имя")).toBeTruthy();
    expect(screen.getByText("Электронная почта")).toBeTruthy();
    expect(screen.getByText("Номер телефона")).toBeTruthy();
    expect(screen.getByText("Резюме")).toBeTruthy();
    unmountRu();
  });

  it("formats boolean and string Yes/No choices appropriately", async () => {
    const answers: ApplicantAnswer[] = [
      { field_id: "1", key: "relocate", label: "Willing to relocate?", type: "boolean", value: true },
      { field_id: "2", key: "remote", label: "Remote only?", type: "text", value: "Yes" },
      { field_id: "3", key: "visa", label: "Needs visa?", type: "text", value: "no" },
    ];

    // English
    const { unmount } = renderWithLang(<ApplicationAnswers answers={answers} />, "en");
    await waitFor(() => {
      expect(screen.getAllByText("Yes").length).toBe(2);
    });
    expect(screen.getByText("No")).toBeTruthy();
    unmount();

    // Uzbek
    const { unmount: unmountUz } = renderWithLang(<ApplicationAnswers answers={answers} />, "uz");
    await waitFor(() => {
      expect(screen.getAllByText("Ha").length).toBe(2);
    });
    expect(screen.getByText("Yo'q")).toBeTruthy();
    unmountUz();

    // Russian
    const { unmount: unmountRu } = renderWithLang(<ApplicationAnswers answers={answers} />, "ru");
    await waitFor(() => {
      expect(screen.getAllByText("Да").length).toBe(2);
    });
    expect(screen.getByText("Нет")).toBeTruthy();
    unmountRu();
  });
});

