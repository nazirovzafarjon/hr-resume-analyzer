import type { ReactNode } from "react";

type ErrorStateProps = {
  /** Human-friendly headline ("Something went wrong"). */
  title?: string;
  /** What happened and what the user can do about it. */
  message: string;
  /** Optional retry/other action. */
  action?: ReactNode;
};

/**
 * Inline error banner for a failed section load. Deliberately message-first:
 * technical detail belongs in the console, not in the product UI.
 */
export default function ErrorState({ title, message, action }: ErrorStateProps) {
  return (
    <div className="error-state" role="alert">
      <p className="error-state-message">
        {title && <strong>{title} </strong>}
        {message}
      </p>
      {action && <div className="error-state-action">{action}</div>}
    </div>
  );
}
