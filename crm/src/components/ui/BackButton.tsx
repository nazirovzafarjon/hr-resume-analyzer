import { useCallback, type ReactNode } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowLeft } from "lucide-react";
import { useLanguage } from "../../contexts/LanguageContext";

export interface SmartBackOptions {
  /** Whether the current page has uncommitted/unsaved changes */
  isDirty?: boolean;
  /** Custom confirmation prompt message if dirty */
  confirmMessage?: string;
  /** Custom extra callback executed before or along with navigation */
  onNavigate?: () => void;
}

/**
 * Hook providing smart history navigation:
 * 1. Checks if the view is dirty; if so, displays a confirmation dialog.
 * 2. If user confirms (or not dirty), checks if browser history exists in this session (`window.history.state.idx > 0`).
 * 3. Navigates back (`navigate(-1)`) if history exists, preserving query params and filters.
 * 4. Otherwise, navigates to `fallbackPath`.
 */
export function useSmartBack(fallbackPath: string, options?: SmartBackOptions) {
  const navigate = useNavigate();
  const { t } = useLanguage();

  return useCallback(() => {
    if (options?.isDirty) {
      const message =
        options.confirmMessage ||
        t("common.unsavedChangesPrompt") ||
        t("common.unsavedChanges") ||
        "You have unsaved changes. Are you sure you want to leave without saving?";
      const ok = typeof window !== "undefined" ? window.confirm(message) : true;
      if (!ok) return;
    }

    options?.onNavigate?.();

    const hasHistory =
      typeof window !== "undefined" &&
      typeof window.history?.state?.idx === "number" &&
      window.history.state.idx > 0;

    if (hasHistory) {
      navigate(-1);
    } else {
      navigate(fallbackPath);
    }
  }, [fallbackPath, options, navigate, t]);
}

export interface BackButtonProps {
  /** Explicit fallback route path when no history exists in this session (e.g. direct entry/refresh) */
  fallbackPath: string;
  /** Custom label. If omitted, defaults to localized "Back" */
  label?: ReactNode;
  /** Whether the current form or view has unsaved changes */
  isDirty?: boolean;
  /** Custom confirmation message when isDirty is true */
  confirmMessage?: string;
  /** Optional click handler invoked before back navigation */
  onClick?: () => void;
  /** Additional CSS class names */
  className?: string;
  /** Button style variant matching design tokens */
  variant?: "ghost" | "secondary" | "link";
  /** Button size */
  size?: "sm" | "md";
  /** Icon size in pixels */
  iconSize?: number;
  /** When true, renders icon only */
  iconOnly?: boolean;
  /** Accessible label */
  ariaLabel?: string;
  /** Custom title attribute */
  title?: string;
}

/**
 * Standardized Back navigation button for all detail, create, edit, and sub-pages.
 *
 * CRITICAL REQUIREMENTS:
 * - Explicitly renders with `type="button"` to ensure it never submits an enclosing `<form>`.
 * - Confirms before leaving if `isDirty` is true.
 * - Navigates back via `navigate(-1)` to preserve previous filters, query params and scroll position,
 *   falling back safely to `fallbackPath` if the user landed directly on the page.
 */
export default function BackButton({
  fallbackPath,
  label,
  isDirty = false,
  confirmMessage,
  onClick,
  className,
  variant = "ghost",
  size = "sm",
  iconSize = 15,
  iconOnly = false,
  ariaLabel,
  title,
}: BackButtonProps) {
  const { t } = useLanguage();
  const handleSmartBack = useSmartBack(fallbackPath, { isDirty, confirmMessage, onNavigate: onClick });

  const defaultLabel = t("common.back") || "Back";
  const displayLabel = label ?? defaultLabel;
  const accessibleName = ariaLabel || (typeof displayLabel === "string" ? displayLabel : "Back");

  const classes = [
    "btn",
    `btn--${variant}`,
    size !== "md" ? `btn--${size}` : null,
    iconOnly ? "btn--icon" : null,
    "back-button",
    className,
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <button
      type="button"
      className={classes}
      onClick={handleSmartBack}
      aria-label={accessibleName}
      title={title || (iconOnly ? accessibleName : undefined)}
    >
      <span className="btn-label">
        <ArrowLeft size={iconSize} aria-hidden="true" />
        {!iconOnly && displayLabel}
      </span>
    </button>
  );
}
