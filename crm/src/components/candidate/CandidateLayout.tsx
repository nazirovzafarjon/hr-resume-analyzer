import type { ReactNode } from "react";
import { NavLink, useNavigate } from "react-router-dom";
import { CalendarDays, FileText, LayoutDashboard, LogOut, UserRound } from "lucide-react";
import ThemeToggle from "../ui/ThemeToggle";
import LanguageSelector from "../ui/LanguageSelector";
import { useLanguage } from "../../contexts/LanguageContext";
import { useCandidateAuth } from "../../context/CandidateAuthContext";
import { candidateImageUrl } from "./portalFormat";
import "../../styles/app.css";
import "../../styles/candidate.css";

// TODO(CANDIDATE-PORTAL): "Messages" (candidate <-> HR) and an AI assistant
// are planned as later phases; add them here as nav items once they have a
// backend. They are intentionally not shown as disabled placeholders.
const NAV = [
  { to: "/candidate", labelKey: "portal.nav.dashboard", icon: LayoutDashboard, end: true },
  { to: "/candidate/applications", labelKey: "portal.nav.applications", icon: FileText },
  { to: "/candidate/interviews", labelKey: "portal.nav.interviews", icon: CalendarDays },
  { to: "/candidate/profile", labelKey: "portal.nav.profile", icon: UserRound },
];

function initials(name: string): string {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase())
    .join("");
}

/**
 * Shell of the Candidate Portal: a calm top bar with four destinations
 * (a personal workspace, not the HR console). On small screens the
 * navigation becomes a scrollable tab row under the header.
 */
export default function CandidateLayout({ children }: { children: ReactNode }) {
  const { t } = useLanguage();
  const { profile, signOut } = useCandidateAuth();
  const navigate = useNavigate();
  const image = candidateImageUrl(profile?.profile_image ?? null);

  async function handleSignOut() {
    await signOut();
    navigate("/candidate/login");
  }

  return (
    <div className="portal">
      <a className="skip-link" href="#portal-main">
        {t("portal.skipToContent")}
      </a>
      <header className="portal-header">
        <div className="portal-header-inner">
          <NavLink to="/candidate" className="portal-brand" end>
            <span className="auth-brand-mark" aria-hidden="true">
              RA
            </span>
            <span className="portal-brand-text">
              <span className="portal-brand-name">{t("app.name")}</span>
              <span className="portal-brand-tag">{t("portal.tagline")}</span>
            </span>
          </NavLink>

          <nav className="portal-nav" aria-label={t("portal.nav.label")}>
            {NAV.map(({ to, labelKey, icon: Icon, end }) => (
              <NavLink
                key={to}
                to={to}
                end={end}
                className={({ isActive }) => `portal-nav-link${isActive ? " portal-nav-link--active" : ""}`}
              >
                <Icon size={16} aria-hidden="true" />
                <span>{t(labelKey)}</span>
              </NavLink>
            ))}
          </nav>

          <div className="portal-toolbar">
            <ThemeToggle />
            <LanguageSelector compact />
            <span className="portal-avatar" aria-hidden="true">
              {image ? <img src={image} alt="" /> : initials(profile?.full_name ?? "")}
            </span>
            <button type="button" className="portal-signout" onClick={handleSignOut}>
              <LogOut size={16} aria-hidden="true" />
              <span>{t("portal.signOut")}</span>
            </button>
          </div>
        </div>
      </header>

      <main id="portal-main" className="portal-main" tabIndex={-1}>
        {children}
      </main>
    </div>
  );
}
