import { AlertTriangle } from "lucide-react";
import Button from "./Button";
import Modal from "./Modal";

type ConfirmDialogProps = {
  open: boolean;
  title: string;
  message: string;
  confirmLabel: string;
  cancelLabel?: string;
  loading?: boolean;
  disabled?: boolean;
  /** Renders the destructive styling (icon + danger button). Default true. */
  danger?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
};

/**
 * Confirmation dialog for destructive or irreversible actions.
 *
 * Always rendered instead of `window.confirm()` so the wording, focus handling
 * and dark mode stay under our control — and so the destructive choice is
 * visually distinguishable from Cancel.
 */
export default function ConfirmDialog({
  open,
  title,
  message,
  confirmLabel,
  cancelLabel = "Cancel",
  loading = false,
  disabled = false,
  danger = true,
  onConfirm,
  onCancel,
}: ConfirmDialogProps) {
  return (
    <Modal
      open={open}
      title={title}
      onClose={onCancel}
      size="sm"
      busy={loading}
      footer={
        <>
          <Button variant="secondary" onClick={onCancel} disabled={loading || disabled}>
            {cancelLabel}
          </Button>
          <Button
            variant={danger ? "danger" : "primary"}
            onClick={onConfirm}
            loading={loading}
            disabled={disabled}
          >
            {confirmLabel}
          </Button>
        </>
      }
    >
      <div className="confirm-danger">
        {danger && (
          <span className="confirm-danger-icon" aria-hidden="true">
            <AlertTriangle size={18} />
          </span>
        )}
        <p className="modal-message">{message}</p>
      </div>
    </Modal>
  );
}
