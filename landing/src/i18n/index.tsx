import { createContext, useCallback, useContext, useEffect, type ReactNode } from "react";
import { en, type Dictionary } from "./en";
import { ru } from "./ru";
import { uz } from "./uz";
import { kiril } from "./kiril";
import { HTML_LANG, pagePath, type Language, type Page } from "../lib/routes";

export type { Language } from "../lib/routes";

export const LANGUAGES: { code: Language; label: string; short: string }[] = [
  { code: "uz", label: "O'zbekcha", short: "UZ" },
  { code: "kiril", label: "Ўзбекча", short: "ЎЗ" },
  { code: "ru", label: "Русский", short: "RU" },
  { code: "en", label: "English", short: "EN" },
];

// Every dictionary is typed against `en`, so a missing key fails the build.
export const DICTIONARIES: Record<Language, Dictionary> = { en, ru, uz, kiril };

// Shared with the CRM so the choice carries over when both apps share an origin.
// index.html reads it to send returning visitors from "/" to their language.
export const LANGUAGE_STORAGE_KEY = "resume-analyzer-language";

type I18nContextValue = {
  language: Language;
  page: Page;
  /** Navigates to the current page in another language. */
  setLanguage: (language: Language) => void;
  /** Site-relative URL of the home page in the current language ("/" or "/ru/"). */
  homeHref: string;
  /** Site-relative URL of another page in the current language. */
  href: (page: "privacy" | "terms") => string;
  t: Dictionary;
};

const I18nContext = createContext<I18nContextValue | undefined>(undefined);

/**
 * Typed, statically bundled translations. The language comes from the URL
 * (see lib/routes.ts) so every language is a real, crawlable page; components
 * read strings as plain properties (`t.hero.title`).
 */
export function I18nProvider({
  language,
  page,
  children,
}: {
  language: Language;
  page: Page;
  children: ReactNode;
}) {
  useEffect(() => {
    document.documentElement.lang = HTML_LANG[language];
  }, [language]);

  const setLanguage = useCallback(
    (next: Language) => {
      try {
        localStorage.setItem(LANGUAGE_STORAGE_KEY, next);
      } catch {
        /* preference just won't persist */
      }
      if (next === language) return;
      // A 404 has no localized twin; send the visitor to that language's home page.
      const target = pagePath(next, page === "notFound" ? "home" : page);
      window.location.assign(`${target}${window.location.hash}`);
    },
    [language, page],
  );

  const value: I18nContextValue = {
    language,
    page,
    setLanguage,
    homeHref: pagePath(language, "home"),
    href: (target) => pagePath(language, target),
    t: DICTIONARIES[language],
  };

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n(): I18nContextValue {
  const context = useContext(I18nContext);
  if (!context) throw new Error("useI18n must be used within an I18nProvider");
  return context;
}
