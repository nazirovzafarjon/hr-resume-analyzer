import type { ReactNode } from "react";

type EmptyStateProps = {
  title: string;
  message: string;
  /** Primary call to action. */
  action?: ReactNode;
  /** Optional secondary action (e.g. "Refresh"). */
  secondaryAction?: ReactNode;
  /** Icon shown in the tinted square. Defaults to a neutral document glyph. */
  icon?: ReactNode;
  /** "error" switches the icon tint to the error palette. */
  tone?: "neutral" | "error";
  className?: string;
};

const DEFAULT_ICON = (
  <svg
    width="24"
    height="24"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="1.6"
    strokeLinecap="round"
    strokeLinejoin="round"
    aria-hidden="true"
  >
    <path d="M5 3h9l5 5v13H5z" />
    <path d="M14 3v5h5" />
    <path d="M9 13h6M9 17h4" />
  </svg>
);

/**
 * Friendly empty state. Used for "no data yet" and, with `tone="error"`, for
 * recoverable load failures — always with a clear next step when one exists.
 */
export default function EmptyState({
  title,
  message,
  action,
  secondaryAction,
  icon,
  tone = "neutral",
  className,
}: EmptyStateProps) {
  return (
    <div
      className={[
        "empty-state",
        tone === "error" ? "empty-state--error" : null,
        className,
      ]
        .filter(Boolean)
        .join(" ")}
    >
      <div className="empty-state-icon" aria-hidden="true">
        {icon ?? DEFAULT_ICON}
      </div>
      <h3 className="empty-state-title">{title}</h3>
      <p className="empty-state-message">{message}</p>
      {(action || secondaryAction) && (
        <div className="empty-state-action">
          {action}
          {secondaryAction}
        </div>
      )}
    </div>
  );
}
