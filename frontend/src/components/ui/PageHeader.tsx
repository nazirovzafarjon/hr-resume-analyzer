import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { ChevronRight } from "lucide-react";

type Crumb = {
  label: string;
  /** When set, the crumb renders as a link. */
  to?: string;
};

type PageHeaderProps = {
  title: string;
  description?: string;
  action?: ReactNode;
  /** Optional breadcrumb trail rendered above the title. */
  breadcrumbs?: Crumb[];
};

/**
 * Consistent page heading used across every application page: optional
 * breadcrumbs, title, one-line description and the primary page action.
 */
export default function PageHeader({
  title,
  description,
  action,
  breadcrumbs,
}: PageHeaderProps) {
  return (
    <header className="page-header">
      <div className="page-header-text">
        {breadcrumbs && breadcrumbs.length > 0 && (
          <nav className="breadcrumbs" aria-label="Breadcrumb">
            {breadcrumbs.map((crumb, index) => (
              <span
                key={`${crumb.label}-${index}`}
                style={{ display: "inline-flex", alignItems: "center", gap: "4px" }}
              >
                {index > 0 && (
                  <span className="breadcrumbs-separator" aria-hidden="true">
                    <ChevronRight size={12} />
                  </span>
                )}
                {crumb.to ? (
                  <Link to={crumb.to}>{crumb.label}</Link>
                ) : (
                  <span className="breadcrumbs-current">{crumb.label}</span>
                )}
              </span>
            ))}
          </nav>
        )}
        <h1 className="page-title">{title}</h1>
        {description && <p className="page-description">{description}</p>}
      </div>
      {action && <div className="page-header-action">{action}</div>}
    </header>
  );
}
