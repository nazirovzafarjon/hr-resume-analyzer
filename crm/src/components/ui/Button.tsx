import type { ButtonHTMLAttributes, ReactNode } from "react";
import { Link } from "react-router-dom";

type Variant = "primary" | "secondary" | "danger" | "danger-subtle" | "ghost" | "link";
type Size = "sm" | "md" | "lg";

type CommonProps = {
  children?: ReactNode;
  variant?: Variant;
  size?: Size;
  /** Optional leading icon (any node, rendered before the label). */
  icon?: ReactNode;
  /** Stretch to the width of the container. */
  block?: boolean;
  /** Icon-only square button; pass `ariaLabel` for accessibility. */
  iconOnly?: boolean;
  loading?: boolean;
  className?: string;
  ariaLabel?: string;
  title?: string;
};

type ButtonAsButton = CommonProps & {
  to?: undefined;
  onClick?: ButtonHTMLAttributes<HTMLButtonElement>["onClick"];
  type?: "button" | "submit";
  disabled?: boolean;
};

type ButtonAsLink = CommonProps & {
  /** Render as an internal link (e.g. `to="/jobs/create"`) instead of a button. */
  to: string;
  disabled?: boolean;
};

type ButtonProps = ButtonAsButton | ButtonAsLink;

/**
 * The single action button for the whole product.
 *
 * Geometry is identical across variants and sizes, and the loading spinner is
 * absolutely positioned over a hidden label — so pressing "Save" never makes
 * the button (or the row it sits in) jump.
 */
export default function Button({
  children,
  variant = "primary",
  size = "md",
  icon,
  block = false,
  iconOnly = false,
  loading = false,
  className,
  ariaLabel,
  title,
  ...rest
}: ButtonProps) {
  const classes = [
    "btn",
    `btn--${variant}`,
    size !== "md" ? `btn--${size}` : null,
    block ? "btn--block" : null,
    iconOnly ? "btn--icon" : null,
    className,
  ]
    .filter(Boolean)
    .join(" ");

  const content = (
    <>
      {loading && <span className="btn-spinner" aria-hidden="true" />}
      <span className="btn-label">
        {icon}
        {children}
      </span>
    </>
  );

  if ("to" in rest && rest.to) {
    const { to, disabled } = rest;
    return (
      <Link
        className={classes}
        to={disabled ? "#" : to}
        aria-label={ariaLabel}
        title={title}
        aria-disabled={disabled || undefined}
        tabIndex={disabled ? -1 : undefined}
        onClick={(event) => {
          if (disabled) event.preventDefault();
        }}
      >
        {content}
      </Link>
    );
  }

  const { onClick, type = "button", disabled = false } = rest as ButtonAsButton;

  return (
    <button
      type={type}
      className={classes}
      onClick={onClick}
      disabled={disabled || loading}
      aria-label={ariaLabel}
      aria-busy={loading || undefined}
      title={title}
    >
      {content}
    </button>
  );
}
