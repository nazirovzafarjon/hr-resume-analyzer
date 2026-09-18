import type { ReactNode } from "react";

type AuthCardProps = {
  title: string;
  subtitle?: string;
  children: ReactNode;
  /** Optional secondary navigation below the form (e.g. "Go to login"). */
  footer?: ReactNode;
  /** Wider card for pages with extra content (reset-password choices). */
  wide?: boolean;
};

/** Surface card with the page heading, supporting text and form content. */
export default function AuthCard({ title, subtitle, children, footer, wide }: AuthCardProps) {
  return (
    <section className={`auth-card${wide ? " auth-card--wide" : ""}`}>
      <h1 className="auth-title">{title}</h1>
      {subtitle && <p className="auth-subtitle">{subtitle}</p>}
      {children}
      {footer && (
        <nav className="auth-nav" aria-label="Authentication pages">
          {footer}
        </nav>
      )}
    </section>
  );
}
