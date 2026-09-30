import { useState } from "react";
import ConfirmDialog from "../ui/ConfirmDialog";
import { useLanguage } from "../../contexts/LanguageContext";
import { useNotify } from "../../contexts/ToastContext";
import { deleteAdminUser, updateAdminUser } from "../../services/adminService";
import { getErrorMessage } from "../../utils/apiError";

export type UserAction = "activate" | "deactivate" | "promote" | "demote" | "delete";

type Target = { id: number; full_name: string; email: string };

const DESTRUCTIVE: Record<UserAction, boolean> = {
  activate: false,
  deactivate: true,
  promote: false,
  demote: true,
  delete: true,
};

function perform(action: UserAction, id: number): Promise<unknown> {
  switch (action) {
    case "activate":
      return updateAdminUser(id, { is_active: true });
    case "deactivate":
      return updateAdminUser(id, { is_active: false });
    case "promote":
      return updateAdminUser(id, { is_superuser: true });
    case "demote":
      return updateAdminUser(id, { is_superuser: false });
    case "delete":
      return deleteAdminUser(id);
  }
}

/**
 * Confirmation for every account-level admin action. Each action explains
 * its consequence before it runs; the server still enforces the rules
 * (e.g. no self-demotion) and its message is shown if it refuses.
 */
export default function UserActionDialog({
  pending,
  onClose,
  onDone,
}: {
  pending: { action: UserAction; user: Target } | null;
  onClose: () => void;
  onDone: (action: UserAction) => void;
}) {
  const { t } = useLanguage();
  const notify = useNotify();
  const [busy, setBusy] = useState(false);

  if (!pending) return null;
  const { action, user } = pending;
  const name = user.full_name || user.email;

  async function confirm() {
    setBusy(true);
    try {
      await perform(action, user.id);
      notify.success(t(`admin.users.actions.${action}.done`, { name }));
      onDone(action);
    } catch (error) {
      notify.error(t("admin.users.actionFailed"), getErrorMessage(error));
    } finally {
      setBusy(false);
    }
  }

  return (
    <ConfirmDialog
      open
      danger={DESTRUCTIVE[action]}
      title={t(`admin.users.actions.${action}.title`)}
      message={t(`admin.users.actions.${action}.message`, { name, email: user.email })}
      confirmLabel={t(`admin.users.actions.${action}.confirm`)}
      cancelLabel={t("common.cancel")}
      loading={busy}
      onConfirm={confirm}
      onCancel={onClose}
    />
  );
}
