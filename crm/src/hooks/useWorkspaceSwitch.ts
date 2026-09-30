import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { useLanguage } from "../contexts/LanguageContext";
import { useNotify } from "../contexts/ToastContext";
import { ApiError } from "../utils/apiError";
import type { SessionRole } from "../types/auth";

/**
 * Switch the current session to another workspace (account menu, admin
 * sidebar). The server issues a new session for the requested workspace —
 * only if the account really has it — and revokes the old one; nothing is
 * decided in the browser.
 */
export function useWorkspaceSwitch() {
  const { switchRole } = useAuth();
  const navigate = useNavigate();
  const notify = useNotify();
  const { t } = useLanguage();
  const [switching, setSwitching] = useState(false);

  /** Switch to `role`, then open `destination` (default: the workspace home). */
  async function switchTo(role: SessionRole, destination?: string) {
    if (switching) return;
    setSwitching(true);
    try {
      const next = await switchRole(role);
      notify.success(t(`workspace.switched.${role}`));
      navigate(destination ?? next, { replace: true });
    } catch (error) {
      const forbidden = error instanceof ApiError && error.status === 403;
      notify.error(
        t("workspace.switchFailed"),
        forbidden ? t("workspace.notAvailable") : undefined,
      );
    } finally {
      setSwitching(false);
    }
  }

  return { switchTo, switching };
}
