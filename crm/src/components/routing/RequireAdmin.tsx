import { useEffect, type ReactNode } from "react";
import { Navigate } from "react-router-dom";
import { useAuth } from "../../context/AuthContext";
import { useLanguage } from "../../contexts/LanguageContext";
import { useNotify } from "../../contexts/ToastContext";
import { SESSION_ROLES } from "../../types/auth";

/**
 * Guards the admin console: it renders only in an admin session.
 *
 * - no session -> /login (or the pending workspace choice),
 * - HR session -> /dashboard (an administrator can switch workspace from
 *   the account menu; a regular HR account never sees the console).
 *
 * This is a UX convenience only: every /api/admin endpoint independently
 * requires an admin account *and* an admin session, whatever the URL,
 * query string or browser storage says.
 */
export default function RequireAdmin({ children }: { children: ReactNode }) {
  const { isAuthenticated, pendingSelection, activeRole } = useAuth();
  const notify = useNotify();
  const { t } = useLanguage();
  const denied = isAuthenticated && activeRole !== SESSION_ROLES.ADMIN;

  useEffect(() => {
    if (denied) notify.error(t("admin.accessDenied"));
  }, [denied, notify, t]);

  if (!isAuthenticated) return <Navigate to={pendingSelection ? "/select-role" : "/login"} replace />;
  if (denied) return <Navigate to="/dashboard" replace />;
  return <>{children}</>;
}
