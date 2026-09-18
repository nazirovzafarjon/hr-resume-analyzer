import type { MouseEventHandler, ReactNode } from "react";

type AuthButtonProps = {
  children: ReactNode;
  /** Shows the spinner and disables the button to prevent double submits. */
  loading?: boolean;
  disabled?: boolean;
  type?: "submit" | "button";
  fullWidth?: boolean;
  /** Visual weight. "secondary" is the quieter outline style. */
  variant?: "primary" | "secondary";
  /** Required for `type="button"` actions (e.g. "Skip", "Back"). */
  onClick?: MouseEventHandler<HTMLButtonElement>;
};

/**
 * Primary (orange) action button for auth forms.
 *
 * Mirrors the shared <Button /> geometry, and keeps the same loading behaviour:
 * the label is hidden while the spinner overlays it, so the button never
 * changes size (and the form never shifts).
 */
export default function AuthButton({
  children,
  loading = false,
  disabled = false,
  type = "submit",
  fullWidth = false,
  variant = "primary",
  onClick,
}: AuthButtonProps) {
  return (
    <button
      type={type}
      className={`btn btn--${variant}${fullWidth ? " btn--block" : ""}`}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      onClick={onClick}
    >
      {loading && <span className="btn-spinner" aria-hidden="true" />}
      <span className="btn-label">{children}</span>
    </button>
  );
}
