import {
  BarChart3,
  Bell,
  Bot,
  Briefcase,
  CalendarDays,
  FileText,
  HeartPulse,
  LayoutDashboard,
  ScrollText,
  Settings as SettingsIcon,
  TriangleAlert,
  UserCog,
  UserRound,
} from "lucide-react";
import type { NavGroup } from "./Sidebar";

/** Admin console navigation: overview → management → insights → monitoring → configuration. */
export const ADMIN_NAV_GROUPS: NavGroup[] = [
  { items: [{ to: "/admin/dashboard", labelKey: "admin.nav.dashboard", icon: LayoutDashboard }] },
  {
    labelKey: "admin.nav.groupManagement",
    items: [
      { to: "/admin/users", labelKey: "admin.nav.users", icon: UserCog },
      { to: "/admin/jobs", labelKey: "admin.nav.jobs", icon: Briefcase },
      { to: "/admin/applications", labelKey: "admin.nav.applications", icon: FileText },
      { to: "/admin/candidates", labelKey: "admin.nav.candidates", icon: UserRound },
      { to: "/admin/interviews", labelKey: "admin.nav.interviews", icon: CalendarDays },
      { to: "/admin/notifications", labelKey: "admin.nav.notifications", icon: Bell },
    ],
  },
  {
    labelKey: "admin.nav.groupInsights",
    items: [{ to: "/admin/analytics", labelKey: "admin.nav.analytics", icon: BarChart3 }],
  },
  {
    labelKey: "admin.nav.groupMonitoring",
    items: [
      { to: "/admin/ai-analysis", labelKey: "admin.nav.aiAnalysis", icon: Bot },
      { to: "/admin/audit-logs", labelKey: "admin.nav.auditLogs", icon: ScrollText },
      { to: "/admin/system-errors", labelKey: "admin.nav.systemErrors", icon: TriangleAlert },
      { to: "/admin/system-health", labelKey: "admin.nav.systemHealth", icon: HeartPulse },
    ],
  },
  {
    labelKey: "admin.nav.groupConfiguration",
    items: [{ to: "/admin/settings", labelKey: "admin.nav.settings", icon: SettingsIcon }],
  },
];

/** Header title for the active admin route (translation key). */
export function adminTitleKey(pathname: string): string {
  if (/^\/admin\/users\/\d+/.test(pathname)) return "admin.users.detailTitle";
  if (/^\/admin\/(applications|candidates)\/\d+/.test(pathname)) return "admin.applications.detailTitle";
  if (pathname.startsWith("/admin/notifications")) return "admin.notifications.title";
  const match = ADMIN_NAV_GROUPS.flatMap((group) => group.items).find((item) =>
    pathname.startsWith(item.to),
  );
  return match?.labelKey ?? "admin.nav.dashboard";
}
