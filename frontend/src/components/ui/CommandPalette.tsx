import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { useNavigate } from "react-router-dom";
import {
  BarChart3,
  Briefcase,
  CalendarDays,
  FileText,
  LayoutDashboard,
  Monitor,
  Moon,
  Search,
  Settings as SettingsIcon,
  Sun,
  Users,
} from "lucide-react";
import { useLanguage, LANGUAGE_LABELS, type Language } from "../../contexts/LanguageContext";
import { useTheme } from "../../contexts/ThemeContext";

type CommandPaletteProps = {
  open: boolean;
  onClose: () => void;
};

type PaletteAction = {
  id: string;
  group: string;
  label: string;
  icon: ReactNode;
  keywords: string;
  run: () => void;
};

const LANGUAGES: Language[] = ["uz", "en", "ru", "kiril"];

/**
 * Ctrl/Cmd + K command palette: jump between the main HR areas, switch theme
 * and switch language without hunting through menus.
 *
 * Intentionally tiny — a filtered list over a static action array, no extra
 * dependency and no fuzzy-search library. The open state is owned by AppLayout
 * so the header search button and the keyboard shortcut share one source.
 */
export default function CommandPalette({ open, onClose }: CommandPaletteProps) {
  const navigate = useNavigate();
  const { t, setLanguage } = useLanguage();
  const { setTheme } = useTheme();

  const [query, setQuery] = useState("");
  const [highlight, setHighlight] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  const actions = useMemo<PaletteAction[]>(() => {
    const go = (path: string) => () => {
      navigate(path);
      onClose();
    };

    const navItems: { id: string; path: string; label: string; icon: ReactNode }[] = [
      { id: "dashboard", path: "/dashboard", label: t("nav.dashboard"), icon: <LayoutDashboard size={16} /> },
      { id: "jobs", path: "/jobs", label: t("nav.jobs"), icon: <Briefcase size={16} /> },
      { id: "applications", path: "/applications", label: t("nav.applications"), icon: <FileText size={16} /> },
      { id: "candidates", path: "/candidates", label: t("nav.candidates"), icon: <Users size={16} /> },
      { id: "interviews", path: "/interviews", label: t("nav.interviews"), icon: <CalendarDays size={16} /> },
      { id: "analytics", path: "/analytics", label: t("nav.analytics"), icon: <BarChart3 size={16} /> },
      { id: "settings", path: "/settings", label: t("nav.settings"), icon: <SettingsIcon size={16} /> },
    ];

    const navigation: PaletteAction[] = navItems.map((item) => ({
      id: item.id,
      group: t("palette.groupNavigation"),
      label: item.label,
      icon: item.icon,
      keywords: `${item.label} ${item.id}`,
      run: go(item.path),
    }));

    const themeItems = [
      { id: "theme-light", label: t("settings.themeLight"), icon: <Sun size={16} />, value: "light" as const },
      { id: "theme-dark", label: t("settings.themeDark"), icon: <Moon size={16} />, value: "dark" as const },
      { id: "theme-system", label: t("settings.themeSystem"), icon: <Monitor size={16} />, value: "system" as const },
    ];

    const appearance: PaletteAction[] = themeItems.map((item) => ({
      id: item.id,
      group: t("palette.groupAppearance"),
      label: item.label,
      icon: item.icon,
      keywords: `${item.label} theme appearance rejim mavzu тема`,
      run: () => {
        setTheme(item.value);
        onClose();
      },
    }));

    const languages: PaletteAction[] = LANGUAGES.map((code) => ({
      id: `lang-${code}`,
      group: t("palette.groupLanguage"),
      label: LANGUAGE_LABELS[code],
      icon: <span aria-hidden="true">{code === "kiril" ? "КИР" : code.toUpperCase()}</span>,
      keywords: `${LANGUAGE_LABELS[code]} ${code}`,
      run: () => {
        setLanguage(code);
        onClose();
      },
    }));

    return [...navigation, ...appearance, ...languages];
  }, [t, navigate, onClose, setLanguage, setTheme]);

  const results = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return actions;
    return actions.filter((action) => action.keywords.toLowerCase().includes(q));
  }, [actions, query]);

  // Reset and focus every time the palette opens.
  useEffect(() => {
    if (!open) return;
    setQuery("");
    setHighlight(0);
    const frame = window.requestAnimationFrame(() => inputRef.current?.focus());
    return () => window.cancelAnimationFrame(frame);
  }, [open]);

  useEffect(() => {
    setHighlight(0);
  }, [query]);

  if (!open) return null;

  function handleKeyDown(event: React.KeyboardEvent<HTMLDivElement>) {
    if (event.key === "Escape") {
      event.preventDefault();
      onClose();
      return;
    }

    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      if (results.length === 0) return;
      const delta = event.key === "ArrowDown" ? 1 : -1;
      setHighlight((current) => (current + delta + results.length) % results.length);
      return;
    }

    if (event.key === "Enter") {
      event.preventDefault();
      results[highlight]?.run();
    }
  }

  let lastGroup = "";

  return (
    <div
      className="palette-backdrop"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <div
        className="palette"
        role="dialog"
        aria-modal="true"
        aria-label={t("palette.title")}
        onKeyDown={handleKeyDown}
      >
        <div className="palette-search">
          <Search size={16} aria-hidden="true" />
          <input
            ref={inputRef}
            className="palette-input"
            type="text"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder={t("palette.placeholder")}
            aria-label={t("palette.placeholder")}
            autoComplete="off"
            spellCheck={false}
          />
          <kbd>Esc</kbd>
        </div>

        {results.length === 0 ? (
          <p className="palette-empty">{t("palette.noResults")}</p>
        ) : (
          <ul className="palette-list" role="listbox" aria-label={t("palette.title")}>
            {results.map((action, index) => {
              const showGroup = action.group !== lastGroup;
              lastGroup = action.group;
              return (
                <li key={action.id}>
                  {showGroup && <p className="palette-group-label">{action.group}</p>}
                  <button
                    type="button"
                    role="option"
                    aria-selected={index === highlight}
                    className={`palette-item${index === highlight ? " is-highlighted" : ""}`}
                    onMouseEnter={() => setHighlight(index)}
                    onClick={action.run}
                  >
                    <span className="palette-item-icon">{action.icon}</span>
                    <span className="palette-item-label">{action.label}</span>
                  </button>
                </li>
              );
            })}
          </ul>
        )}

        <div className="palette-footer">
          <span className="palette-hint">
            <kbd>↑</kbd>
            <kbd>↓</kbd>
            {t("palette.hintNavigate")}
          </span>
          <span className="palette-hint">
            <kbd>↵</kbd>
            {t("palette.hintSelect")}
          </span>
        </div>
      </div>
    </div>
  );
}