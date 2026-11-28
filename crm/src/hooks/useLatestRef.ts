import { useLayoutEffect, useRef } from "react";

/**
 * A ref that always holds the latest committed `value`.
 *
 * For callbacks and effects that must read the current value without
 * re-subscribing when it changes. The ref is updated after commit rather than
 * during render: a render React throws away (concurrent rendering, Strict
 * Mode) must never leave its value behind. Layout effects run before regular
 * effects of the same commit, so `useEffect` callbacks see the new value.
 */
export function useLatestRef<T>(value: T) {
  const ref = useRef(value);
  useLayoutEffect(() => {
    ref.current = value;
  });
  return ref;
}
