import type { ReactNode } from "react";

type AuthMessageType = "error" | "success";

type AuthMessageProps = {
  type: AuthMessageType;
  children: ReactNode;
};

/**
 * Page-level feedback banner. Errors use role="alert" (announced
 * immediately), success uses role="status" (announced politely).
 */
export default function AuthMessage({ type, children }: AuthMessageProps) {
  return (
    <div
      className={`alert alert--${type}`}
      role={type === "error" ? "alert" : "status"}
    >
      {type === "error" ? <ErrorIcon /> : <SuccessIcon />}
      <span>{children}</span>
    </div>
  );
}

function ErrorIcon() {
  return (
    <svg
      width="16"
      height="16"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <circle cx="12" cy="12" r="10" />
      <line x1="12" y1="8" x2="12" y2="12" />
      <line x1="12" y1="16" x2="12.01" y2="16" />
    </svg>
  );
}

function SuccessIcon() {
  return (
    <svg
      width="16"
      height="16"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
      <polyline points="22 4 12 14.01 9 11.01" />
    </svg>
  );
}
