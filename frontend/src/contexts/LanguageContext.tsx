import { createContext, useContext, useState, useCallback, useEffect, type ReactNode } from "react";

export type Language = "uz" | "en" | "ru" | "kiril";

type LanguageContextValue = {
  language: Language;
  setLanguage: (lang: Language) => void;
  t: (key: string, params?: Record<string, string | number>) => string;
  isLoading: boolean;
};

const LanguageContext = createContext<LanguageContextValue | undefined>(undefined);

const LANGUAGE_STORAGE_KEY = "resume-analyzer-language";

const LANGUAGE_LABELS: Record<Language, string> = {
  uz: "O'zbekcha",
  en: "English",
  ru: "Русский",
  kiril: "Ўзбекча",
};

function getPreferredLanguage(): Language {
  if (typeof window !== "undefined") {
    const stored = localStorage.getItem(LANGUAGE_STORAGE_KEY);
    if (stored === "uz" || stored === "en" || stored === "ru" || stored === "kiril") {
      return stored;
    }
  }
  return "en";
}

function deepGet(obj: unknown, path: string): string | undefined {
  const keys = path.split(".");
  let current: unknown = obj;
  
  for (const key of keys) {
    if (current && typeof current === "object" && key in current) {
      current = (current as Record<string, unknown>)[key];
    } else {
      return undefined;
    }
  }
  
  return typeof current === "string" ? current : undefined;
}

function interpolate(template: string, params?: Record<string, string | number>): string {
  if (!params) return template;
  return template.replace(/\{(\w+)\}/g, (_, key) => {
    return params[key]?.toString() ?? `{${key}}`;
  });
}

type TranslationModules = Record<Language, Record<string, unknown>>;

async function loadAllTranslations(): Promise<TranslationModules> {
  try {
    const files = [
      "", // base: app name, nav
      "-ui", // shell, status labels, palette, toasts, settings extras
      "-auth",
      "-dashboard",
      "-jobs",
      "-applications",
      "-candidates",
      "-interviews",
      "-analytics",
      "-settings",
      "-common",
    ];

    const loadLangModule = async (lang: Language) => {
      const modules = await Promise.all(
        files.map(suffix => import(`../translations/${lang}${suffix}.json`).then(m => m.default))
      );

      // Merge all modules into one object
      const merged: Record<string, unknown> = {};
      for (const mod of modules) {
        if (mod) {
          for (const key of Object.keys(mod)) {
            merged[key] = mod[key];
          }
        }
      }
      return merged;
    };

    const [en, uz, ru, kiril] = await Promise.all([
      loadLangModule("en"),
      loadLangModule("uz"),
      loadLangModule("ru"),
      loadLangModule("kiril"),
    ]);

    return { en, uz, ru, kiril };
  } catch (e) {
    console.error("Failed to load translations:", e);
    return { en: {}, uz: {}, ru: {}, kiril: {} };
  }
}

export function LanguageProvider({ children }: { children: ReactNode }) {
  const [language, setLanguageState] = useState<Language>(getPreferredLanguage);
  const [translations, setTranslations] = useState<TranslationModules>({ en: {}, uz: {}, ru: {}, kiril: {} });
  const [isLoading, setIsLoading] = useState(true);

  // All four language packs are fetched once, up front: switching language is
  // then a pure state update, so the whole UI re-renders instantly with no
  // network round-trip.
  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      const all = await loadAllTranslations();
      if (cancelled) return;
      setTranslations(all);
      setIsLoading(false);
    };
    load();
    return () => {
      cancelled = true;
    };
  }, []);

  // Keep the document language in sync (screen readers, spellcheck, hyphenation).
  useEffect(() => {
    if (typeof document === "undefined") return;
    document.documentElement.lang =
      language === "kiril" ? "uz-Cyrl" : language === "uz" ? "uz" : language;
  }, [language]);

  const setLanguage = useCallback((lang: Language) => {
    setLanguageState(lang);
    if (typeof localStorage !== "undefined") {
      localStorage.setItem(LANGUAGE_STORAGE_KEY, lang);
    }
  }, []);

  const t = useCallback(
    (key: string, params?: Record<string, string | number>): string => {
      const translation = deepGet(translations, `${language}.${key}`) 
        || deepGet(translations, `en.${key}`)
        || key;
      return interpolate(translation as string, params);
    },
    [translations, language]
  );

  return (
    <LanguageContext.Provider value={{ language, setLanguage, t, isLoading }}>
      {children}
    </LanguageContext.Provider>
  );
}

export function useLanguage(): LanguageContextValue {
  const context = useContext(LanguageContext);
  if (!context) {
    throw new Error("useLanguage must be used within a LanguageProvider");
  }
  return context;
}

export { LANGUAGE_LABELS };