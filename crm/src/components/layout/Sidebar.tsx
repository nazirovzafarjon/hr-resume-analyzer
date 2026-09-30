import { NavLink } from "react-router-dom";
import {
  ArrowLeftRight,
  BarChart3,
  Briefcase,
  CalendarDays,
  ChevronsLeft,
  FileText,
  House,
  LayoutDashboard,
  Settings as SettingsIcon,
  ShieldCheck,
  Users,
  type LucideIcon,
} from "lucide-react";
import Tooltip from "../ui/Tooltip";
import { useLanguage } from "../../contexts/LanguageContext";
import { useAuth } from "../../context/AuthContext";
import { useWorkspaceSwitch } from "../../hooks/useWorkspaceSwitch";
import { SESSION_ROLES } from "../../types/auth";
import { LANDING_URL } from "../../config";
import { ADMIN_NAV_GROUPS } from "./adminNavigation";

export type ShellVariant = "hr" | "admin";

type SidebarProps = {
  open: boolean;
  collapsed: boolean;
  onClose: () => void;
  onToggleCollapse: () => void;
  /** "admin" swaps in the admin console navigation. */
  variant?: ShellVariant;
};

export type NavItem = {
  to: string;
  /** Translation key of the label. */
  labelKey: string;
  icon: LucideIcon;
  end?: boolean;
};

export type NavGroup = {
  /** Translation key for the group heading; the first group has none. */
  labelKey?: string;
  items: NavItem[];
};

/** Shortcut to the console, shown on HR pages during an admin session. */
const ADMIN_ENTRY: NavItem = { to: "/admin", labelKey: "admin.nav.openAdmin", icon: ShieldCheck };

/** Navigation grouped by the HR workflow: overview → recruitment → insights → system. */
const NAV_GROUPS: NavGroup[] = [
  { items: [{ to: "/dashboard", labelKey: "nav.dashboard", icon: LayoutDashboard, end: true }] },
  {
    labelKey: "shell.navGroup.recruitment",
    items: [
      { to: "/jobs", labelKey: "nav.jobs", icon: Briefcase },
      { to: "/applications", labelKey: "nav.applications", icon: FileText },
      { to: "/candidates", labelKey: "nav.candidates", icon: Users },
      { to: "/interviews", labelKey: "nav.interviews", icon: CalendarDays },
    ],
  },
  { labelKey: "shell.navGroup.insights", items: [{ to: "/analytics", labelKey: "nav.analytics", icon: BarChart3 }] },
  { labelKey: "shell.navGroup.system", items: [{ to: "/settings", labelKey: "nav.settings", icon: SettingsIcon }] },
];

/**
 * Left-hand navigation for the authenticated app.
 *
 * Desktop: persistent sidebar that can collapse to an icon rail (tooltips keep
 * destinations identifiable). Tablet/mobile: off-canvas drawer behind a
 * backdrop, closed by navigation or Escape.
 */
export default function Sidebar({
  open,
  collapsed,
  onClose,
  onToggleCollapse,
  variant = "hr",
}: SidebarProps) {
  const { t } = useLanguage();
  const { activeRole } = useAuth();
  const { switchTo, switching } = useWorkspaceSwitch();
  const isAdminShell = variant === "admin";

  // Only an admin *session* gets the console link. An administrator working
  // in the HR workspace switches workspace from the account menu instead.
  // Only a shortcut: the admin routes and API check the session themselves.
  const groups: NavGroup[] = isAdminShell
    ? ADMIN_NAV_GROUPS
    : activeRole === SESSION_ROLES.ADMIN
      ? NAV_GROUPS.map((group, index) =>
          index === NAV_GROUPS.length - 1 ? { ...group, items: [...group.items, ADMIN_ENTRY] } : group,
        )
      : NAV_GROUPS;
  const homePath = isAdminShell ? "/admin/dashboard" : "/dashboard";

  return (
    <>
      {open && (
        <button
          type="button"
          className="sidebar-backdrop"
          onClick={onClose}
          aria-label={t("shell.closeNavigation")}
          tabIndex={-1}
        />
      )}

      <nav
        className={[
          "sidebar",
          open ? "sidebar--open" : "",
          collapsed ? "sidebar--collapsed" : "",
        ]
          .filter(Boolean)
          .join(" ")}
        aria-label={isAdminShell ? t("admin.nav.label") : t("shell.mainNavigation")}
      >
        <div className="sidebar-brand">
          <NavLink to={homePath} className="sidebar-brand-link">
            <span
              className={`sidebar-brand-mark${isAdminShell ? " sidebar-brand-mark--admin" : ""}`}
              aria-hidden="true"
            >
              RA
            </span>
            <span className="sidebar-brand-text">
              <span className="sidebar-brand-name">{t("app.name")}</span>
              <span className="sidebar-brand-tag">
                {isAdminShell ? t("admin.nav.tagline") : t("app.tagline")}
              </span>
            </span>
          </NavLink>
        </div>

        <div className="sidebar-nav">
          {groups.map((group, groupIndex) => {
            const headingId = group.labelKey ? `sidebar-group-${groupIndex}` : undefined;
            return (
              <div key={groupIndex} className="sidebar-group">
                {group.labelKey && (
                  <p id={headingId} className="sidebar-group-label">
                    {t(group.labelKey)}
                  </p>
                )}
                <ul aria-labelledby={headingId}>
                  {group.items.map((item) => {
                    const Icon = item.icon;
                    const label = t(item.labelKey);
                    return (
                      <li key={item.to}>
                        <Tooltip label={collapsed && !open ? label : null} side="right">
                          <NavLink
                            to={item.to}
                            end={item.end}
                            className={({ isActive }) =>
                              `sidebar-link${isActive ? " is-active" : ""}`
                            }
                            onClick={onClose}
                          >
                            <span className="sidebar-link-icon" aria-hidden="true">
                              <Icon size={18} />
                            </span>
                            <span className="sidebar-link-label">{label}</span>
                          </NavLink>
                        </Tooltip>
                      </li>
                    );
                  })}
                </ul>
              </div>
            );
          })}
        </div>

        {/* HR shell: leaves for the public landing site (session kept).
            Admin shell: switches this session to the HR workspace. */}
        <div className="sidebar-exit">
          {isAdminShell ? (
            <Tooltip label={collapsed && !open ? t("workspace.switchToHr") : null} side="right">
              <button
                type="button"
                className="sidebar-link sidebar-link--button"
                onClick={() => switchTo(SESSION_ROLES.USER)}
                disabled={switching}
              >
                <span className="sidebar-link-icon" aria-hidden="true">
                  <ArrowLeftRight size={18} />
                </span>
                <span className="sidebar-link-label">{t("workspace.switchToHr")}</span>
              </button>
            </Tooltip>
          ) : (
            <Tooltip label={collapsed && !open ? t("shell.backToHome") : null} side="right">
              <a href={LANDING_URL} className="sidebar-link">
                <span className="sidebar-link-icon" aria-hidden="true">
                  <House size={18} />
                </span>
                <span className="sidebar-link-label">{t("shell.backToHome")}</span>
              </a>
            </Tooltip>
          )}
        </div>

        <div className="sidebar-footer">
          <SidebarCollapseToggle collapsed={collapsed} onToggle={onToggleCollapse} />
        </div>
      </nav>
    </>
  );
}

/** Collapse affordance, kept separate so it only renders on desktop. */
export function SidebarCollapseToggle({
  collapsed,
  onToggle,
}: {
  collapsed: boolean;
  onToggle: () => void;
}) {
  const { t } = useLanguage();
  return (
    <button
      type="button"
      className="sidebar-collapse-toggle"
      onClick={onToggle}
      aria-label={collapsed ? t("shell.expandSidebar") : t("shell.collapseSidebar")}
      aria-pressed={collapsed}
      title={collapsed ? t("shell.expandSidebar") : t("shell.collapseSidebar")}
    >
      <ChevronsLeft
        size={16}
        aria-hidden="true"
        style={{
          transform: collapsed ? "scaleX(-1)" : undefined,
          transition: "transform var(--transition-fast)",
        }}
      />
    </button>
  );
}
