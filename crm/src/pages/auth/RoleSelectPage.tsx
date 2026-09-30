import { useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import { ArrowRight, Briefcase, ShieldCheck, type LucideIcon } from "lucide-react";
import AuthLayout from "../../components/auth/AuthLayout";
import AuthCard from "../../components/auth/AuthCard";
import AuthMessage from "../../components/auth/AuthMessage";
import PageMeta from "../../components/seo/PageMeta";
import { landingPath, useAuth } from "../../context/AuthContext";
import { useLanguage } from "../../contexts/LanguageContext";
import { ApiError } from "../../utils/apiError";
import { SESSION_ROLES, type SessionRole } from "../../types/auth";

const WORKSPACES: { role: SessionRole; icon: LucideIcon; key: "hr" | "admin" }[] = [
  { role: SESSION_ROLES.USER, icon: Briefcase, key: "hr" },
  { role: SESSION_ROLES.ADMIN, icon: ShieldCheck, key: "admin" },
];

/**
 * Workspace choice for accounts that have more than one (HR + admin).
 *
 * Shown only after a sign-in that returned `requires_role_selection`; the
 * choice is sent to the server, which issues a session for that workspace
 * only if the account really has it. Nothing here grants access by itself.
 */
export default function RoleSelectPage() {
  const { t } = useLanguage();
  const navigate = useNavigate();
  const { pendingSelection, isAuthenticated, activeRole, selectRole, signOut } = useAuth();
  const [busyRole, setBusyRole] = useState<SessionRole | null>(null);
  const [error, setError] = useState<{ message: string; expired: boolean } | null>(null);

  if (!pendingSelection) {
    // Reloaded, or opened directly: nothing to choose (the selection token is
    // kept in memory only), so continue the session or sign in again.
    return <Navigate to={isAuthenticated ? landingPath(activeRole) : "/login"} replace />;
  }

  const expired = Date.now() >= pendingSelection.expiresAt;
  const firstName = pendingSelection.fullName.trim().split(/\s+/)[0] ?? "";

  async function choose(role: SessionRole) {
    setBusyRole(role);
    setError(null);
    try {
      navigate(await selectRole(role), { replace: true });
    } catch (err) {
      const status = err instanceof ApiError ? err.status : 0;
      setError(
        status === 401
          ? { message: t("workspace.expired"), expired: true }
          : status === 403
            ? { message: t("workspace.notAvailable"), expired: false }
            : { message: t("workspace.selectFailed"), expired: false },
      );
      setBusyRole(null);
    }
  }

  function signInAgain() {
    signOut();
    navigate("/login", { replace: true });
  }

  return (
    <AuthLayout>
      <PageMeta title={t("workspace.chooseTitle")} noindex />
      <AuthCard
        wide
        title={firstName ? t("workspace.welcomeName", { name: firstName }) : t("workspace.welcome")}
        subtitle={t("workspace.chooseSubtitle")}
        footer={
          <button type="button" className="auth-link auth-link--button" onClick={signInAgain}>
            {t("workspace.useAnotherAccount")}
          </button>
        }
      >
        {(error || expired) && (
          <AuthMessage type="error">
            {error?.message ?? t("workspace.expired")}{" "}
            {(expired || error?.expired) && (
              <button type="button" className="auth-link auth-link--button" onClick={signInAgain}>
                {t("workspace.signInAgain")}
              </button>
            )}
          </AuthMessage>
        )}

        <div className="workspace-options" role="group" aria-label={t("workspace.chooseTitle")}>
          {WORKSPACES.filter(({ role }) => pendingSelection.availableRoles.includes(role)).map(
            ({ role, icon: Icon, key }) => (
              <button
                key={role}
                type="button"
                className="workspace-option"
                onClick={() => choose(role)}
                disabled={busyRole !== null || expired}
                aria-busy={busyRole === role}
              >
                <span className={`workspace-option-icon workspace-option-icon--${key}`} aria-hidden="true">
                  <Icon size={20} />
                </span>
                <span className="workspace-option-text">
                  <span className="workspace-option-title">{t(`workspace.${key}.title`)}</span>
                  <span className="workspace-option-description">{t(`workspace.${key}.description`)}</span>
                </span>
                <span className="workspace-option-action">
                  {t(`workspace.${key}.continue`)}
                  {busyRole === role ? (
                    <span className="workspace-option-spinner" aria-hidden="true" />
                  ) : (
                    <ArrowRight size={16} aria-hidden="true" />
                  )}
                </span>
              </button>
            ),
          )}
        </div>
        <p className="workspace-hint">{t("workspace.hint")}</p>
      </AuthCard>
    </AuthLayout>
  );
}
