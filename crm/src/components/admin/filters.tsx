import { useEffect, useState } from "react";
import { fetchFilterOptions } from "../../services/adminService";
import { useLanguage } from "../../contexts/LanguageContext";
import type { FilterOptions } from "../../types/admin";

type Option = { value: string; label: string };

/** A labelled <select> sized for the FilterBar toolbar. */
export function ToolbarSelect({
  label,
  value,
  onChange,
  options,
  allLabel,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  options: Option[];
  /** Label of the empty ("no filter") option; omit to require a value. */
  allLabel?: string;
}) {
  return (
    <label className="toolbar-label">
      {label}
      <select className="field-select" value={value} onChange={(event) => onChange(event.target.value)}>
        {allLabel !== undefined && <option value="">{allLabel}</option>}
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </label>
  );
}

/** "From / To" calendar-date inputs (inclusive range, sent as YYYY-MM-DD). */
export function DateRangeFields({
  from,
  to,
  onChange,
}: {
  from: string;
  to: string;
  onChange: (range: { date_from: string; date_to: string }) => void;
}) {
  const { t } = useLanguage();
  return (
    <>
      <label className="toolbar-label">
        {t("admin.filters.from")}
        <input
          type="date"
          className="field-input"
          value={from}
          max={to || undefined}
          onChange={(event) => onChange({ date_from: event.target.value, date_to: to })}
        />
      </label>
      <label className="toolbar-label">
        {t("admin.filters.to")}
        <input
          type="date"
          className="field-input"
          value={to}
          min={from || undefined}
          onChange={(event) => onChange({ date_from: from, date_to: event.target.value })}
        />
      </label>
    </>
  );
}

// Owner/company options change rarely; one request serves every admin page
// visited in the session.
let optionsRequest: Promise<FilterOptions> | null = null;

/** HR owners and companies for the filter dropdowns (empty while loading). */
export function useFilterOptions(): FilterOptions {
  const [options, setOptions] = useState<FilterOptions>({ owners: [], companies: [] });
  useEffect(() => {
    let cancelled = false;
    optionsRequest ??= fetchFilterOptions().catch((error: unknown) => {
      optionsRequest = null;
      throw error;
    });
    optionsRequest
      .then((result) => {
        if (!cancelled) setOptions(result);
      })
      .catch(() => {
        /* Filters simply stay empty; the list itself still loads. */
      });
    return () => {
      cancelled = true;
    };
  }, []);
  return options;
}

export function OwnerSelect({ value, onChange }: { value: string; onChange: (value: string) => void }) {
  const { t } = useLanguage();
  const { owners } = useFilterOptions();
  return (
    <ToolbarSelect
      label={t("admin.filters.owner")}
      value={value}
      onChange={onChange}
      allLabel={t("labels.all")}
      options={owners.map((owner) => ({ value: String(owner.id), label: owner.full_name || owner.email }))}
    />
  );
}

export function CompanySelect({ value, onChange }: { value: string; onChange: (value: string) => void }) {
  const { t } = useLanguage();
  const { companies } = useFilterOptions();
  return (
    <ToolbarSelect
      label={t("admin.filters.company")}
      value={value}
      onChange={onChange}
      allLabel={t("labels.all")}
      options={companies.map((company) => ({ value: company, label: company }))}
    />
  );
}

/** Header-click handler for server sorting: same column flips, new column sorts descending. */
export function nextSort(
  current: { sort: string; order: string },
  key: string,
): { sort: string; order: "asc" | "desc" } {
  if (current.sort === key) return { sort: key, order: current.order === "asc" ? "desc" : "asc" };
  return { sort: key, order: "desc" };
}

/** Local state for a search box that writes to the URL after a short pause. */
export function useSearchInput(urlValue: string, commit: (value: string) => void, delayMs = 350) {
  const [value, setValue] = useState(urlValue);
  // Follow external changes (e.g. "Clear filters") without fighting typing.
  useEffect(() => setValue(urlValue), [urlValue]);
  useEffect(() => {
    if (value === urlValue) return;
    const timer = window.setTimeout(() => commit(value.trim()), delayMs);
    return () => window.clearTimeout(timer);
  }, [value, urlValue, commit, delayMs]);
  return [value, setValue] as const;
}
