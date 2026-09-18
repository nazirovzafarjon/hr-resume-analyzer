import type { ReactNode } from "react";

type CardProps = {
  children: ReactNode;
  title?: string;
  subtitle?: string;
  /** Header action on the right (a link, button or menu). */
  action?: ReactNode;
  /** Leading icon shown before the title. */
  icon?: ReactNode;
  className?: string;
  /** Remove the inner padding (e.g. when the card contains a full-bleed table). */
  flush?: boolean;
  /** Hover affordance for cards that are themselves clickable. */
  interactive?: boolean;
};

/**
 * Surface container with an optional header. The one card primitive used by
 * every page, so padding, border radius and header rhythm never drift.
 */
export default function Card({
  children,
  title,
  subtitle,
  action,
  icon,
  className,
  flush = false,
  interactive = false,
}: CardProps) {
  const classes = [
    "card",
    flush ? "card--flush" : null,
    interactive ? "card--interactive" : null,
    className,
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <section className={classes}>
      {(title || action) && (
        <header className="card-header">
          <div className="card-header-text">
            {title && (
              <h2 className="card-title">
                {icon && (
                  <span
                    style={{
                      display: "inline-flex",
                      verticalAlign: "-3px",
                      marginRight: "8px",
                      color: "var(--color-text-muted)",
                    }}
                    aria-hidden="true"
                  >
                    {icon}
                  </span>
                )}
                {title}
              </h2>
            )}
            {subtitle && <p className="card-subtitle">{subtitle}</p>}
          </div>
          {action && <div className="card-action">{action}</div>}
        </header>
      )}
      {children}
    </section>
  );
}
