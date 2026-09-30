import { useCallback, useEffect, useState, type ReactNode } from "react";
import { useLocation } from "react-router-dom";
import "../../styles/app.css";
import "../../styles/admin.css";
import Header from "./Header";
import Sidebar, { type ShellVariant } from "./Sidebar";
import { adminTitleKey } from "./adminNavigation";
import CommandPalette from "../ui/CommandPalette";
import { useLanguage } from "../../contexts/LanguageContext";

/** Where the collapsed-rail preference is stored. */
const SIDEBAR_COLLAPSED_KEY = "resume-analyzer-sidebar-collapsed";

function prefersCollapsed(): boolean {
  if (typeof window === "undefined") return false;
  return window.localStorage.getItem(SIDEBAR_COLLAPSED_KEY) === "true";
}

/** Resolve the header title for the active route. */
function useHeaderTitle(variant: ShellVariant): string {
  const { pathname } = useLocation();
  const { t } = useLanguage();

  if (variant === "admin") return t(adminTitleKey(pathname));

  return pathname.startsWith("/jobs/create")
    ? t("pages.createJob")
    : /^\/jobs\/\d+\/edit$/.test(pathname)
      ? t("pages.editJob")
      : /^\/jobs\/\d+/.test(pathname)
        ? t("pages.jobDetails")
        : /^\/candidates\/\d+/.test(pathname)
          ? t("pages.candidateDetails")
          : /^\/applications\/\d+/.test(pathname)
            ? t("pages.applicationDetails")
            : /^\/interviews\/\d+/.test(pathname)
              ? t("pages.interviewDetails")
              : pathname.startsWith("/jobs")
                ? t("nav.jobs")
                : pathname.startsWith("/candidates")
                  ? t("nav.candidates")
                  : pathname.startsWith("/applications")
                    ? t("nav.applications")
                    : pathname.startsWith("/interviews")
                      ? t("nav.interviews")
                      : pathname.startsWith("/analytics")
                        ? t("nav.analytics")
                        : pathname.startsWith("/settings")
                          ? t("nav.settings")
                          : t("nav.dashboard");
}

/**
 * Authenticated application shell: persistent sidebar + sticky header around
 * the page content, plus the global command palette.
 *
 * The rail collapses on desktop (preference persisted) and becomes an
 * off-canvas drawer below 900px, closed automatically after navigation.
 *
 * `variant="admin"` renders the same shell with the admin console navigation,
 * so the admin panel shares the product's layout, theming and behaviour.
 */
export default function AppLayout({
  children,
  variant = "hr",
}: {
  children: ReactNode;
  variant?: ShellVariant;
}) {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [collapsed, setCollapsed] = useState<boolean>(() =>
    typeof window === "undefined" ? false : window.innerWidth > 900 ? prefersCollapsed() : false,
  );
  const [paletteOpen, setPaletteOpen] = useState(false);
  const location = useLocation();
  const title = useHeaderTitle(variant);
  const { t } = useLanguage();

  // Close the mobile drawer automatically after navigating.
  useEffect(() => {
    setSidebarOpen(false);
  }, [location.pathname]);

  // Mobile drawer: focus moves into it on open; Escape closes it and returns
  // focus to the menu button, so keyboard users are never stranded.
  useEffect(() => {
    if (!sidebarOpen) return;
    document.querySelector<HTMLElement>(".sidebar--open .sidebar-link")?.focus();
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key !== "Escape") return;
      setSidebarOpen(false);
      document.querySelector<HTMLElement>(".header-menu-button")?.focus();
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [sidebarOpen]);

  // Global keyboard shortcut: Ctrl/Cmd + K opens the command palette.
  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent) {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setPaletteOpen((open) => !open);
      }
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  const toggleCollapse = useCallback(() => {
    setCollapsed((current) => {
      const next = !current;
      try {
        window.localStorage.setItem(SIDEBAR_COLLAPSED_KEY, String(next));
      } catch {
        /* Private mode: the preference simply is not persisted. */
      }
      return next;
    });
  }, []);

  return (
    <div
      className={`app-shell${collapsed ? " app-shell--collapsed" : ""}${
        variant === "admin" ? " app-shell--admin" : ""
      }`}
    >
      <a className="skip-link" href="#app-content">
        {t("shell.skipToContent")}
      </a>

      <Sidebar
        open={sidebarOpen}
        collapsed={collapsed}
        onClose={() => setSidebarOpen(false)}
        onToggleCollapse={toggleCollapse}
        variant={variant}
      />

      <div className="app-body">
        <Header
          onMenuClick={() => setSidebarOpen((open) => !open)}
          menuOpen={sidebarOpen}
          onOpenPalette={() => setPaletteOpen(true)}
          title={title}
          variant={variant}
        />
        <main id="app-content" className="app-content">
          {children}
        </main>
      </div>

      <CommandPalette open={paletteOpen} onClose={() => setPaletteOpen(false)} />
    </div>
  );
}
