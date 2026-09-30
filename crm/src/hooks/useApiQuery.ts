import { useCallback, useEffect, useRef, useState } from "react";

type ApiQueryState<T> = {
  data: T | null;
  loading: boolean;
  error: unknown;
  /** Re-run the request with the same inputs (the "Try again" button). */
  reload: () => void;
};

/**
 * Load data for a page section and track loading / error state.
 *
 * `key` identifies the request inputs (e.g. serialized filters): the fetch
 * re-runs whenever it changes. Responses that arrive after a newer request
 * started are ignored, so fast filter changes can never show stale rows.
 * While a refetch is in flight the previous data stays visible.
 */
export function useApiQuery<T>(fetcher: () => Promise<T>, key: string): ApiQueryState<T> {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<unknown>(null);
  const [attempt, setAttempt] = useState(0);
  const fetcherRef = useRef(fetcher);
  fetcherRef.current = fetcher;

  useEffect(() => {
    let current = true;
    setLoading(true);
    setError(null);
    fetcherRef
      .current()
      .then((result) => {
        if (current) setData(result);
      })
      .catch((err: unknown) => {
        if (current) setError(err);
      })
      .finally(() => {
        if (current) setLoading(false);
      });
    return () => {
      current = false;
    };
  }, [key, attempt]);

  const reload = useCallback(() => setAttempt((value) => value + 1), []);
  return { data, loading, error, reload };
}
