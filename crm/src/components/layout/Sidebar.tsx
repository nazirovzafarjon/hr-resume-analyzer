import { useEffect, useState } from "react";
import { NavLink, useLocation } from "react-router-dom";
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
  UserCog,
  Users,
  type LucideIcon,
} from "lucide-react";
import Tooltip from "../ui/Tooltip";
import { useLanguage } from "../../contexts/LanguageContext";
import { useAuth } from "../../context/AuthContext";
import { useCurrentUser } from "../../hooks/useCurrentUser";
import { useWorkspaceSwitch } from "../../hooks/useWorkspaceSwitch";
import { SESSION_ROLES } from "../../types/auth";
import { LANDING_URL } from "../../config";
import { ADMIN_NAV_GROUPS } from "./adminNavigation";
import { fetchAdminUnreadNotificationsCount } from "../../services/adminService";

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
  badge?: number | string | null;
};

export type NavGroup = {
  /** Translation key for the group heading; the first group has none. */
  labelKey?: string;
  items: NavItem[];
};

/**
 * Admin shortcuts on HR pages, shown only to accounts the server reports as
 * administrators. User management comes first: it is the admin's core job.
 */
const ADMIN_GROUP: NavGroup = {
  labelKey: "shell.navGroup.admin",
  items: [
    { to: "/admin/users", labelKey: "admin.nav.users", icon: UserCog },
    { to: "/admin/dashboard", labelKey: "admin.nav.openAdmin", icon: ShieldCheck },
  ],
};

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
  const { user } = useCurrentUser();
  const { switchTo, switching } = useWorkspaceSwitch();
  const isAdminShell = variant === "admin";

  // The ADMIN group appears only for an account the backend (/auth/me) says
  // may use the admin workspace. In an admin session its items are plain
  // links; in an HR session they first ask the server to switch the session,
  // which it grants only to a real administrator. Either way this is only a
  // shortcut: the admin routes and API check the session themselves.
  const adminSession = activeRole === SESSION_ROLES.ADMIN;
  const adminAccount = adminSession || (user?.available_roles ?? []).includes(SESSION_ROLES.ADMIN);
  const location = useLocation();
  const [unreadCount, setUnreadCount] = useState<number | null>(null);

  useEffect(() => {
    if (!isAdminShell) return;
    let active = true;
    fetchAdminUnreadNotificationsCount()
      .then((res) => {
        if (active) setUnreadCount(res.unread_count);
      })
      .catch(() => {
        // Non-critical, ignore error in unread badge
      });
    return () => {
      active = false;
    };
  }, [isAdminShell, location.pathname]);

  const baseGroups: NavGroup[] = isAdminShell
    ? ADMIN_NAV_GROUPS
    : adminAccount
      ? [...NAV_GROUPS, ADMIN_GROUP]
      : NAV_GROUPS;

  const groups: NavGroup[] = baseGroups.map((group) => ({
    ...group,
    items: group.items.map((item) =>
      item.to === "/admin/notifications"
        ? { ...item, badge: unreadCount && unreadCount > 0 ? unreadCount : null }
        : item,
    ),
  }));

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
                    const needsSwitch = !isAdminShell && !adminSession && item.to.startsWith("/admin");
                    return (
                      <li key={item.to}>
                        <Tooltip label={collapsed && !open ? label : null} side="right">
                          {needsSwitch ? (
                            <button
                              type="button"
                              className="sidebar-link sidebar-link--button"
                              onClick={() => {
                                onClose();
                                void switchTo(SESSION_ROLES.ADMIN, item.to);
                              }}
                              disabled={switching}
                            >
                              <span className="sidebar-link-icon" aria-hidden="true">
                                <Icon size={18} />
                              </span>
                              <span className="sidebar-link-label">{label}</span>
                              {item.badge !== undefined && item.badge !== null && (
                                <span className="sidebar-link-badge">{item.badge}</span>
                              )}
                            </button>
                          ) : (
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
                              {item.badge !== undefined && item.badge !== null && (
                                <span className="sidebar-link-badge">{item.badge}</span>
                              )}
                            </NavLink>
                          )}
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
