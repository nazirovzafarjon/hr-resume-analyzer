import type { ReactNode } from "react";
import "../../styles/auth.css";
import ThemeToggle from "../ui/ThemeToggle";
import LanguageSelector from "../ui/LanguageSelector";
import { Link } from "react-router-dom";
import { LANDING_URL } from "../../config";
import { useLanguage } from "../../contexts/LanguageContext";

type AuthLayoutProps = {
  children: ReactNode;
};

/**
 * Shared shell for every authentication page: brand header (with theme and
 * language so a visitor can set preferences before signing in), the centered
 * card area and a small footer.
 */
export default function AuthLayout({ children }: AuthLayoutProps) {
  const { t } = useLanguage();

  return (
    <div className="auth-page">
      <div className="auth-topbar">
        <Link to={LANDING_URL} className="auth-brand" aria-label="Home">
          <span className="auth-brand-mark" aria-hidden="true">
            RA
          </span>
          <span className="auth-brand-text">
            <span className="auth-brand-name">{t("app.name")}</span>
            <span className="auth-brand-tag">{t("app.tagline")}</span>
          </span>
        </Link>

        <div className="auth-toolbar">
          <ThemeToggle />
          <LanguageSelector compact />
        </div>
      </div>

      <main className="auth-main">{children}</main>

      <footer className="auth-footer">
        <p>
          © {new Date().getFullYear()} {t("app.name")} · {t("auth.footerNote")}
        </p>
      </footer>
    </div>
  );
}
