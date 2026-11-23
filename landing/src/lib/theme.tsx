import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";

export type ThemePreference = "light" | "dark" | "system";
type ResolvedTheme = "light" | "dark";

type ThemeContextValue = {
  theme: ThemePreference;
  resolvedTheme: ResolvedTheme;
  setTheme: (theme: ThemePreference) => void;
};

// Same key and values as the CRM (crm/src/contexts/ThemeContext.tsx), so the
// preference is shared when both apps are served from one origin.
const STORAGE_KEY = "resume-analyzer-theme";

function readPreference(): ThemePreference {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored === "light" || stored === "dark" || stored === "system") return stored;
  } catch {
    /* storage unavailable (private mode) */
  }
  return "system";
}

const ThemeContext = createContext<ThemeContextValue | undefined>(undefined);

/**
 * Light / dark / system theme, applied as `data-theme` on <html>.
 *
 * The first render always assumes "system" so it matches the prerendered
 * markup; the stored preference is read right after hydration. Until then the
 * inline script in index.html has already put the right `data-theme` on <html>,
 * so nothing is written to the DOM before the real preference is known.
 */
export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setThemeState] = useState<ThemePreference>("system");
  const [system, setSystem] = useState<ResolvedTheme | null>(null);
  const resolvedTheme: ResolvedTheme = theme === "system" ? (system ?? "light") : theme;

  useEffect(() => {
    setThemeState(readPreference());
    const query = window.matchMedia("(prefers-color-scheme: dark)");
    const update = () => setSystem(query.matches ? "dark" : "light");
    update();
    query.addEventListener("change", update);
    return () => query.removeEventListener("change", update);
  }, []);

  useEffect(() => {
    if (system === null) return; // preference not read yet
    document.documentElement.setAttribute("data-theme", resolvedTheme);
  }, [resolvedTheme, system]);

  const setTheme = useCallback((next: ThemePreference) => {
    setThemeState(next);
    try {
      localStorage.setItem(STORAGE_KEY, next);
    } catch {
      /* preference just won't persist */
    }
  }, []);

  return (
    <ThemeContext.Provider value={{ theme, resolvedTheme, setTheme }}>
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme(): ThemeContextValue {
  const context = useContext(ThemeContext);
  if (!context) throw new Error("useTheme must be used within a ThemeProvider");
  return context;
}
