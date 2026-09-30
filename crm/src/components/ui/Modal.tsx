import { useEffect, useId, useRef, type ReactNode } from "react";
import { X } from "lucide-react";
import { useFocusTrap } from "../../hooks/useFocusTrap";

type ModalProps = {
  open: boolean;
  title: string;
  onClose: () => void;
  children: ReactNode;
  /** Optional one-line explanation under the title. */
  description?: string;
  footer?: ReactNode;
  /** Width preset. Use "xl" for editors, "sm" for confirmations. */
  size?: "sm" | "md" | "lg" | "xl";
  /** Blocks Escape/backdrop closing while a submit is in flight. */
  busy?: boolean;
};

/**
 * Accessible modal dialog.
 *
 * Focus moves into the dialog on open and is restored on close, Tab is trapped
 * inside it, Escape and backdrop clicks close it, and the page behind stops
 * scrolling so the dialog cannot be scrolled away. Content is only mounted
 * while open, which keeps the DOM (and any data inside) small.
 */
export default function Modal({
  open,
  title,
  onClose,
  children,
  description,
  footer,
  size = "md",
  busy = false,
}: ModalProps) {
  const titleId = useId();
  const descriptionId = useId();
  const dialogRef = useRef<HTMLDivElement>(null);
  const closeButtonRef = useRef<HTMLButtonElement>(null);

  useFocusTrap(dialogRef, open, { onEscape: onClose, disabled: busy });

  useEffect(() => {
    if (!open) return;
    closeButtonRef.current?.focus();

    const { overflow } = document.body.style;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = overflow;
    };
  }, [open]);

  if (!open) return null;

  return (
    <div
      className="modal-backdrop"
      onMouseDown={(event) => {
        // Only close when the backdrop itself (not the dialog) is clicked.
        if (event.target === event.currentTarget && !busy) onClose();
      }}
    >
      <div
        ref={dialogRef}
        className={`modal modal--${size}`}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={description ? descriptionId : undefined}
      >
        <header className="modal-header">
          <div>
            <h2 id={titleId} className="modal-title">
              {title}
            </h2>
            {description && (
              <p id={descriptionId} className="modal-description">
                {description}
              </p>
            )}
          </div>
          <button
            ref={closeButtonRef}
            type="button"
            className="modal-close"
            onClick={onClose}
            aria-label="Close dialog"
            disabled={busy}
          >
            <X size={16} aria-hidden="true" />
          </button>
        </header>
        <div className="modal-body">{children}</div>
        {footer && <footer className="modal-section-footer">{footer}</footer>}
      </div>
    </div>
  );
}
