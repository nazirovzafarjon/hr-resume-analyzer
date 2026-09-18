import { AlertTriangle, CheckCircle2, Info, X, XCircle } from "lucide-react";
import { useToast, type ToastTone } from "../../contexts/ToastContext";

const TONE_ICONS: Record<ToastTone, typeof Info> = {
  success: CheckCircle2,
  error: XCircle,
  warning: AlertTriangle,
  info: Info,
};
/**
 * Renders the global toast queue in a fixed viewport. Mounted once by the
 * providers, so every page can push notifications without owning UI.
 *
 * Errors are announced assertively (role="alert"), everything else politely
 * (role="status"), and each toast can be dismissed with the keyboard.
 */
export default function Toaster() {
  const { toasts, dismiss } = useToast();

  if (toasts.length === 0) return null;

  return (
    <div className="toast-viewport">
      {toasts.map((toast) => {
        const Icon = TONE_ICONS[toast.tone];
        const assertive = toast.tone === "error";
        return (
          <div
            key={toast.id}
            className={`toast toast--${toast.tone}`}
            role={assertive ? "alert" : "status"}
            aria-live={assertive ? "assertive" : "polite"}
          >
            <span className="toast-icon" aria-hidden="true">
              <Icon size={18} />
            </span>
            <div className="toast-content">
              <p className="toast-title">{toast.title}</p>
              {toast.message && <p className="toast-message">{toast.message}</p>}
            </div>
            <button
              type="button"
              className="toast-close"
              onClick={() => dismiss(toast.id)}
              aria-label="Dismiss notification"
            >
              <X size={14} aria-hidden="true" />
            </button>
          </div>
        );
      })}
    </div>
  );
}