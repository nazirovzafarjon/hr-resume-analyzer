import { useCallback, useMemo } from "react";
import { useSearchParams } from "react-router-dom";

/**
 * List filters, sort and page stored in the URL query string.
 *
 * Keeping them in the URL makes every filtered view linkable (e.g. "this HR
 * user's applications" from the user page is just
 * `/admin/applications?owner_id=7`), survives reloads and works with the
 * browser's back button. Values equal to their default are omitted.
 */
export function useUrlFilters<T extends Record<string, string>>(defaults: T) {
  const [params, setParams] = useSearchParams();

  const values = useMemo(() => {
    const result = { ...defaults } as T;
    for (const key of Object.keys(defaults) as (keyof T & string)[]) {
      const value = params.get(key);
      if (value !== null) (result as Record<string, string>)[key] = value;
    }
    return result;
    // `defaults` is a module-level constant in every caller, so only the URL
    // needs to be a dependency.
  }, [params]);

  const page = Math.max(1, Number.parseInt(params.get("page") ?? "1", 10) || 1);

  /** Change filters; any filter change returns to page 1. */
  const setFilters = useCallback(
    (changes: Partial<T>) => {
      setParams(
        (current) => {
          const next = new URLSearchParams(current);
          for (const [key, value] of Object.entries(changes)) {
            if (value === undefined || value === "" || value === defaults[key]) next.delete(key);
            else next.set(key, String(value));
          }
          next.delete("page");
          return next;
        },
        { replace: true },
      );
    },
    [setParams, defaults],
  );

  const setPage = useCallback(
    (nextPage: number) => {
      setParams((current) => {
        const next = new URLSearchParams(current);
        if (nextPage <= 1) next.delete("page");
        else next.set("page", String(nextPage));
        return next;
      });
    },
    [setParams],
  );

  const clear = useCallback(() => setParams({}, { replace: true }), [setParams]);

  const active = (Object.keys(defaults) as (keyof T & string)[]).some(
    (key) => !["sort", "order"].includes(key) && values[key] !== defaults[key],
  );

  return { values, page, setFilters, setPage, clear, active };
}
