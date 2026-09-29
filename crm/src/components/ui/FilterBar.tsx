import type { ReactNode } from "react";
import { Search, X } from "lucide-react";
import { useLanguage } from "../../contexts/LanguageContext";

type FilterBarProps = {
  search: {
    value: string;
    onChange: (value: string) => void;
    /** Page-specific hint, e.g. "Search by name, email or job…". */
    placeholder: string;
  };
  /** Extra filters (labelled <select>s) shown after the search field. */
  children?: ReactNode;
  /** True when any filter differs from its default — shows "Clear filters". */
  active?: boolean;
  onClear?: () => void;
};

/**
 * The one toolbar layout for list pages: a labelled search field that takes
 * the free space, the page's filters, and a "Clear filters" action that only
 * appears when something is filtered.
 */
export default function FilterBar({ search, children, active = false, onClear }: FilterBarProps) {
  const { t } = useLanguage();
  return (
    <div className="filter-bar" role="search">
      <label className="toolbar-label toolbar-label--grow">
        {t("common.search")}
        <span className="search-field">
          <span className="search-field-icon" aria-hidden="true">
            <Search size={15} />
          </span>
          <input
            className="field-input"
            type="search"
            value={search.value}
            onChange={(event) => search.onChange(event.target.value)}
            placeholder={search.placeholder}
          />
        </span>
      </label>
      {children}
      {active && onClear && (
        <button type="button" className="btn btn--ghost filter-bar-clear" onClick={onClear}>
          <X size={14} aria-hidden="true" />
          {t("common.clearFilters")}
        </button>
      )}
    </div>
  );
}
