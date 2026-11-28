import { useEffect, useState } from "react";

/**
 * True once `deadline` (epoch milliseconds) has passed, and the component
 * re-renders at that moment.
 *
 * Reading `Date.now()` during render gives a value that never updates on its
 * own: a page left open past its deadline kept treating it as in the future.
 * `null` means there is no deadline (never passed).
 */
export function useDeadlinePassed(deadline: number | null): boolean {
  // Which deadline has been seen to pass, so a new deadline starts fresh.
  const [passed, setPassed] = useState<number | null>(() =>
    deadline !== null && Date.now() >= deadline ? deadline : null,
  );

  useEffect(() => {
    if (deadline === null || passed === deadline) return;
    const timer = window.setTimeout(() => setPassed(deadline), Math.max(deadline - Date.now(), 0));
    return () => window.clearTimeout(timer);
  }, [deadline, passed]);

  return deadline !== null && passed === deadline;
}
