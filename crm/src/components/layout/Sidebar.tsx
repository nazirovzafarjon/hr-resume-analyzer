import { NavLink } from "react-router-dom";
import {
  BarChart3,
  Briefcase,
  CalendarDays,
  ChevronsLeft,
  FileText,
  House,
  LayoutDashboard,
  Settings as SettingsIcon,
  Users,
  type LucideIcon,
} from "lucide-react";
import Tooltip from "../ui/Tooltip";
import { useLanguage } from "../../contexts/LanguageContext";
import { LANDING_URL } from "../../config";

type SidebarProps = {
  open: boolean;
  collapsed: boolean;
  onClose: () => void;
  onToggleCollapse: () => void;
};

type NavItem = {
  to: string;
  /** Translation key under `nav.*`. */
  labelKey: string;
  icon: LucideIcon;
  end?: boolean;
};

type NavGroup = {
  /** Translation key for the group heading; the first group has none. */
  labelKey?: string;
  items: NavItem[];
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
}: SidebarProps) {
  const { t } = useLanguage();

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
        aria-label={t("shell.mainNavigation")}
      >
        <div className="sidebar-brand">
          <NavLink to="/dashboard" className="sidebar-brand-link">
            <span className="sidebar-brand-mark" aria-hidden="true">
              RA
            </span>
            <span className="sidebar-brand-text">
              <span className="sidebar-brand-name">{t("app.name")}</span>
              <span className="sidebar-brand-tag">{t("app.tagline")}</span>
            </span>
          </NavLink>
        </div>

        <div className="sidebar-nav">
          {NAV_GROUPS.map((group, groupIndex) => {
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

        {/* Leaves the app for the public landing site; the session is kept. */}
        <div className="sidebar-exit">
          <Tooltip label={collapsed && !open ? t("shell.backToHome") : null} side="right">
            <a href={LANDING_URL} className="sidebar-link">
              <span className="sidebar-link-icon" aria-hidden="true">
                <House size={18} />
              </span>
              <span className="sidebar-link-label">{t("shell.backToHome")}</span>
            </a>
          </Tooltip>
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
