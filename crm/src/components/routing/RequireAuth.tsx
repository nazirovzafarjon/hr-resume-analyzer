import { type ReactNode } from "react";
import { Navigate } from "react-router-dom";
import { useAuth } from "../../context/AuthContext";

/**
 * Guards a page that only signed-in users may open. Visitors in the middle
 * of a multi-workspace sign-in go to the workspace choice; everyone else
 * without a session goes to /login.
 */
export default function RequireAuth({ children }: { children: ReactNode }) {
  const { isAuthenticated, isEmailVerified, pendingSelection } = useAuth();
  if (!isAuthenticated) {
    return <Navigate to={pendingSelection ? "/select-role" : "/login"} replace />;
  }
  // The panel needs a confirmed email; the backend enforces this too, but the
  // guard keeps the user on the verification screen instead of a broken page.
  if (!isEmailVerified) {
    return <Navigate to="/verify-email" replace />;
  }
  return <>{children}</>;
}
