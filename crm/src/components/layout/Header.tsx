import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { LogOut, Menu, Search, Settings as SettingsIcon, UserRound } from "lucide-react";
import Dropdown, { DropdownItem, DropdownLabel, DropdownSeparator } from "../ui/Dropdown";
import ThemeToggle from "../ui/ThemeToggle";
import LanguageSelector from "../ui/LanguageSelector";
import { useAuth } from "../../context/AuthContext";
import { useLanguage } from "../../contexts/LanguageContext";
import { logout } from "../../services/authService";
import { getCurrentUser, profileImageUrl } from "../../services/settingsService";
import { useNotify } from "../../contexts/ToastContext";

type HeaderProps = {
  onMenuClick: () => void;
  onOpenPalette: () => void;
  /** Title shown for the active section (already translated). */
  title: string;
};

function initialsOf(fullName: string): string {
  const parts = fullName.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return "HR";
  return parts
    .slice(0, 2)
    .map((part) => part[0]!.toUpperCase())
    .join("");
}

/**
 * Application top bar: mobile menu, section title, command-palette search and
 * the account area (theme, language, profile). The control set is deliberately
 * small — only what an HR user reaches for during a session.
 */
export default function Header({ onMenuClick, onOpenPalette, title }: HeaderProps) {
  const { signOut } = useAuth();
  const { t } = useLanguage();
  const notify = useNotify();
  const navigate = useNavigate();

  const [profile, setProfile] = useState<{
    name: string;
    email: string;
    image: string | null;
  } | null>(null);

  // Load the profile once so the menu can greet the signed-in user. Failures
  // are silent: the menu falls back to a neutral label.
  useEffect(() => {
    let cancelled = false;
    getCurrentUser()
      .then((user) => {
        if (cancelled) return;
        setProfile({
          name: user.full_name || "",
          email: user.email || "",
          image: profileImageUrl(user.profile_image),
        });
      })
      .catch(() => {
        /* keep the fallback */
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const displayName = profile?.name || t("shell.fallbackName");
  const email = profile?.email || "";

  async function handleLogout() {
    try {
      await logout();
    } catch {
      // Even if the backend logout fails, sign out locally so the token is
      // never left behind.
    }
    signOut();
    notify.info(t("toast.loggedOut"));
    navigate("/login");
  }

  return (
    <header className="app-header">
      <button
        type="button"
        className="header-menu-button"
        onClick={onMenuClick}
        aria-label={t("shell.toggleNavigation")}
      >
        <Menu size={18} aria-hidden="true" />
      </button>

      <div className="header-title-block">
        <h2 className="header-title">{title}</h2>
        <span className="header-subtitle">{t("app.tagline")}</span>
      </div>

      <button type="button" className="header-search" onClick={onOpenPalette}>
        <Search size={16} aria-hidden="true" />
        <span className="header-search-label">{t("palette.placeholder")}</span>
        <kbd>⌘K</kbd>
      </button>

      <div className="header-actions">
        <ThemeToggle />
        <LanguageSelector />
        <Dropdown
          trigger={({ toggle }) => (
            <button
              type="button"
              className="header-profile-trigger"
              onClick={toggle}
              aria-label={t("shell.accountMenu")}
              title={displayName}
            >
              <span className="header-avatar" aria-hidden="true">
                {profile?.image ? (
                  <img src={profile.image} alt="" />
                ) : (
                  initialsOf(displayName)
                )}
              </span>
              <span className="header-profile-text">
                <span className="header-profile-name">{displayName}</span>
                {email && <span className="header-profile-mail">{email}</span>}
              </span>
            </button>
          )}
        >
          <DropdownLabel>{t("shell.accountMenu")}</DropdownLabel>
          <DropdownItem icon={<UserRound size={16} />} onClick={() => navigate("/settings")}>
            {t("shell.profile")}
          </DropdownItem>
          <DropdownItem icon={<SettingsIcon size={16} />} onClick={() => navigate("/settings")}>
            {t("nav.settings")}
          </DropdownItem>
          <DropdownSeparator />
          <DropdownItem icon={<LogOut size={16} />} danger onClick={handleLogout}>
            {t("auth.logout")}
          </DropdownItem>
        </Dropdown>
      </div>
    </header>
  );
}

