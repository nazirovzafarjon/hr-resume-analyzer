import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  ArrowLeftRight,
  LogOut,
  Menu,
  Search,
  Settings as SettingsIcon,
  ShieldCheck,
  UserRound,
} from "lucide-react";
import Dropdown, { DropdownItem, DropdownLabel, DropdownSeparator } from "../ui/Dropdown";
import ThemeToggle from "../ui/ThemeToggle";
import LanguageSelector from "../ui/LanguageSelector";
import { useAuth } from "../../context/AuthContext";
import { useLanguage } from "../../contexts/LanguageContext";
import { logout } from "../../services/authService";
import { getCurrentUser, profileImageUrl } from "../../services/settingsService";
import { useNotify } from "../../contexts/ToastContext";
import type { ShellVariant } from "./Sidebar";
import { getRefreshToken } from "../../auth/tokenStorage";
import { useWorkspaceSwitch } from "../../hooks/useWorkspaceSwitch";
import { SESSION_ROLES, type SessionRole } from "../../types/auth";

type HeaderProps = {
  onMenuClick: () => void;
  /** Whether the mobile navigation drawer is open (drives aria-expanded). */
  menuOpen?: boolean;
  onOpenPalette: () => void;
  /** Title shown for the active section (already translated). */
  title: string;
  variant?: ShellVariant;
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
export default function Header({
  onMenuClick,
  onOpenPalette,
  title,
  menuOpen = false,
  variant = "hr",
}: HeaderProps) {
  const { signOut, activeRole } = useAuth();
  const { switchTo, switching } = useWorkspaceSwitch();
  const { t } = useLanguage();
  const notify = useNotify();
  const navigate = useNavigate();

  const [profile, setProfile] = useState<{
    name: string;
    email: string;
    image: string | null;
    availableRoles: SessionRole[];
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
          availableRoles: user.available_roles ?? [SESSION_ROLES.USER],
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

  // Offered only to accounts that really have another workspace (from
  // /auth/me); the server re-checks when the switch is requested.
  const otherRole: SessionRole | null =
    profile && profile.availableRoles.length > 1
      ? activeRole === SESSION_ROLES.ADMIN
        ? SESSION_ROLES.USER
        : SESSION_ROLES.ADMIN
      : null;
  const currentWorkspace = activeRole === SESSION_ROLES.ADMIN ? "admin" : "hr";

  async function handleLogout() {
    try {
      // Sends the refresh token so the server revokes the whole session.
      await logout(getRefreshToken());
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
        aria-expanded={menuOpen}
      >
        <Menu size={18} aria-hidden="true" />
      </button>

      <div className="header-title-block">
        {variant === "admin" && <span className="header-admin-badge">{t("admin.badge")}</span>}
        <p className="header-title">{title}</p>
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
          <DropdownLabel>
            {t("workspace.current", { name: t(`workspace.${currentWorkspace}.title`) })}
          </DropdownLabel>
          <DropdownItem icon={<UserRound size={16} />} onClick={() => navigate("/settings")}>
            {t("shell.profile")}
          </DropdownItem>
          <DropdownItem icon={<SettingsIcon size={16} />} onClick={() => navigate("/settings")}>
            {t("nav.settings")}
          </DropdownItem>
          {/* In an admin session the console is one click away from any page. */}
          {variant !== "admin" && activeRole === SESSION_ROLES.ADMIN && (
            <DropdownItem icon={<ShieldCheck size={16} />} onClick={() => navigate("/admin")}>
              {t("admin.nav.openAdmin")}
            </DropdownItem>
          )}
          {otherRole && (
            <DropdownItem
              icon={<ArrowLeftRight size={16} />}
              onClick={() => switchTo(otherRole)}
              disabled={switching}
            >
              {t(otherRole === SESSION_ROLES.ADMIN ? "workspace.switchToAdmin" : "workspace.switchToHr")}
            </DropdownItem>
          )}
          <DropdownSeparator />
          <DropdownItem icon={<LogOut size={16} />} danger onClick={handleLogout}>
            {t("auth.logout")}
          </DropdownItem>
        </Dropdown>
      </div>
    </header>
  );
}

