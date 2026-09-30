import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { en, type Dictionary } from "./en";
import { ru } from "./ru";
import { uz } from "./uz";
import { kiril } from "./kiril";

/** Same language codes as the CRM (crm/src/contexts/LanguageContext.tsx). */
export type Language = "uz" | "en" | "ru" | "kiril";

export const LANGUAGES: { code: Language; label: string; short: string }[] = [
  { code: "uz", label: "O'zbekcha", short: "UZ" },
  { code: "kiril", label: "Ўзбекча", short: "ЎЗ" },
  { code: "ru", label: "Русский", short: "RU" },
  { code: "en", label: "English", short: "EN" },
];

// Every dictionary is typed against `en`, so a missing key fails the build.
const DICTIONARIES: Record<Language, Dictionary> = { en, ru, uz, kiril };

// Shared with the CRM so the choice carries over when both apps share an origin.
const STORAGE_KEY = "resume-analyzer-language";

const HTML_LANG: Record<Language, string> = { en: "en", ru: "ru", uz: "uz", kiril: "uz-Cyrl" };

function isLanguage(value: unknown): value is Language {
  return value === "uz" || value === "en" || value === "ru" || value === "kiril";
}

function readLanguage(): Language {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (isLanguage(stored)) return stored;
  } catch {
    /* storage unavailable */
  }
  const browser = navigator.language?.toLowerCase() ?? "";
  if (browser.startsWith("ru")) return "ru";
  if (browser.startsWith("uz")) return browser.includes("cyrl") ? "kiril" : "uz";
  return "en";
}

type I18nContextValue = {
  language: Language;
  setLanguage: (language: Language) => void;
  t: Dictionary;
};

const I18nContext = createContext<I18nContextValue | undefined>(undefined);

/**
 * Typed, statically bundled translations. Components read strings as plain
 * properties (`t.hero.title`), so there are no string keys to mistype and
 * switching language is an instant re-render.
 */
export function I18nProvider({ children }: { children: ReactNode }) {
  const [language, setLanguageState] = useState<Language>(readLanguage);

  useEffect(() => {
    document.documentElement.lang = HTML_LANG[language];
  }, [language]);

  const setLanguage = useCallback((next: Language) => {
    setLanguageState(next);
    try {
      localStorage.setItem(STORAGE_KEY, next);
    } catch {
      /* preference just won't persist */
    }
  }, []);

  return (
    <I18nContext.Provider value={{ language, setLanguage, t: DICTIONARIES[language] }}>
      {children}
    </I18nContext.Provider>
  );
}

export function useI18n(): I18nContextValue {
  const context = useContext(I18nContext);
  if (!context) throw new Error("useI18n must be used within an I18nProvider");
  return context;
}
