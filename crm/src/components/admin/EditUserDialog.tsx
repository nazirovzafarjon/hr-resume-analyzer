import { useState, type FormEvent } from "react";
import Button from "../ui/Button";
import Modal from "../ui/Modal";
import TextInput from "../forms/TextInput";
import { useLanguage } from "../../contexts/LanguageContext";
import { useNotify } from "../../contexts/ToastContext";
import { updateAdminUser } from "../../services/adminService";
import { getErrorMessage } from "../../utils/apiError";
import type { AdminUserUpdate } from "../../types/admin";
import type { UserAction } from "./UserActionDialog";

type Target = {
  id: number;
  full_name: string;
  email: string;
  is_active: boolean;
  is_superuser: boolean;
};

/**
 * Edits every field `PUT /api/users/{id}` accepts: name, account status and
 * role. Only changed fields are sent, and each status/role change lists its
 * consequence before saving (same wording as the one-click actions).
 *
 * On the admin's own account status and role are locked, mirroring the
 * server rule (no self-deactivation or self-demotion). The server still
 * enforces it and its message is shown inline if it refuses.
 */
export default function EditUserDialog({
  user,
  isSelf,
  onClose,
  onDone,
}: {
  user: Target | null;
  isSelf: boolean;
  onClose: () => void;
  onDone: () => void;
}) {
  if (!user) return null;
  // Keyed on the user so the form starts from their current values each time.
  return <EditUserForm key={user.id} user={user} isSelf={isSelf} onClose={onClose} onDone={onDone} />;
}

function EditUserForm({
  user,
  isSelf,
  onClose,
  onDone,
}: {
  user: Target;
  isSelf: boolean;
  onClose: () => void;
  onDone: () => void;
}) {
  const { t } = useLanguage();
  const notify = useNotify();
  const [name, setName] = useState(user.full_name);
  const [active, setActive] = useState(user.is_active);
  const [admin, setAdmin] = useState(user.is_superuser);
  const [nameError, setNameError] = useState<string | undefined>();
  const [formError, setFormError] = useState<string | undefined>();
  const [busy, setBusy] = useState(false);

  const trimmed = name.trim();
  const changes: AdminUserUpdate = {};
  if (trimmed !== user.full_name) changes.full_name = trimmed;
  if (active !== user.is_active) changes.is_active = active;
  if (admin !== user.is_superuser) changes.is_superuser = admin;
  const unchanged = Object.keys(changes).length === 0;

  const consequences: UserAction[] = [];
  if (changes.is_active !== undefined) consequences.push(active ? "activate" : "deactivate");
  if (changes.is_superuser !== undefined) consequences.push(admin ? "promote" : "demote");
  const displayName = trimmed || user.email;

  async function save(event?: FormEvent) {
    event?.preventDefault();
    if (busy || unchanged) return;
    if (!trimmed) {
      setNameError(t("admin.users.edit.nameRequired"));
      return;
    }
    setBusy(true);
    setFormError(undefined);
    try {
      await updateAdminUser(user.id, changes);
      notify.success(t("admin.users.edit.done", { name: trimmed }));
      onDone();
    } catch (err) {
      setFormError(getErrorMessage(err, t("admin.users.actionFailed")));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal
      open
      title={t("admin.users.edit.title")}
      description={user.email}
      onClose={onClose}
      size="sm"
      busy={busy}
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={busy}>
            {t("common.cancel")}
          </Button>
          <Button onClick={() => save()} loading={busy} disabled={unchanged}>
            {t("admin.users.edit.save")}
          </Button>
        </>
      }
    >
      <form className="admin-edit-form" onSubmit={save} noValidate>
        <TextInput
          label={t("admin.users.edit.fullName")}
          value={name}
          onChange={(value) => {
            setName(value);
            setNameError(undefined);
          }}
          required
          autoComplete="off"
          error={nameError}
          disabled={busy}
        />

        <fieldset className="admin-edit-fieldset" disabled={busy || isSelf}>
          <legend className="field-label">{t("admin.users.edit.status")}</legend>
          <label className="toggle-row">
            <input type="checkbox" checked={active} onChange={(event) => setActive(event.target.checked)} />
            {t("admin.users.edit.activeLabel")}
          </label>
        </fieldset>

        <fieldset className="admin-edit-fieldset radio-list" disabled={busy || isSelf}>
          <legend className="field-label">{t("admin.users.role")}</legend>
          <label className="radio-option">
            <input type="radio" name="user-role" checked={!admin} onChange={() => setAdmin(false)} />
            <span>{t("admin.users.roleHr")}</span>
          </label>
          <label className="radio-option">
            <input type="radio" name="user-role" checked={admin} onChange={() => setAdmin(true)} />
            <span>{t("admin.users.roleAdmin")}</span>
          </label>
        </fieldset>

        {isSelf && <p className="admin-note">{t("admin.users.selfNote")}</p>}

        {consequences.length > 0 && (
          <div className="admin-note" role="status">
            <p className="admin-edit-changes-title">{t("admin.users.edit.changesTitle")}</p>
            <ul className="admin-edit-changes">
              {consequences.map((action) => (
                <li key={action}>{t(`admin.users.actions.${action}.message`, { name: displayName })}</li>
              ))}
            </ul>
          </div>
        )}

        {formError && (
          <p className="admin-error-text" role="alert">
            {formError}
          </p>
        )}
      </form>
    </Modal>
  );
}
