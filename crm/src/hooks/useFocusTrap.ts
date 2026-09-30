import { useEffect, useRef, type RefObject } from "react";

type UseFocusTrapOptions = {
  /** Called on Escape — typically the dialog's close handler. */
  onEscape?: () => void;
  /** Skip Escape handling (e.g. while a submit is in flight). */
  disabled?: boolean;
};

const FOCUSABLE_SELECTOR =
  'a[href], button:not([disabled]), textarea, input, select, [tabindex]:not([tabindex="-1"])';

/**
 * Traps Tab/Shift+Tab focus cycling within `containerRef` while `active`, and
 * restores focus to whatever was focused before activation once it ends.
 * Shared by Modal and CommandPalette so every dialog-like overlay in the app
 * behaves identically for keyboard users.
 *
 * The trap is set up once per activation. `onEscape`/`disabled` are read
 * through refs, so callers can pass an inline `onClose` without the trap
 * restarting on every render: a restart would run the cleanup, which moves
 * focus back to the opener and pulls it out of the input being typed in.
 */
export function useFocusTrap(
  containerRef: RefObject<HTMLElement | null>,
  active: boolean,
  { onEscape, disabled }: UseFocusTrapOptions = {},
) {
  const onEscapeRef = useRef(onEscape);
  const disabledRef = useRef(disabled);
  useEffect(() => {
    onEscapeRef.current = onEscape;
    disabledRef.current = disabled;
  });

  useEffect(() => {
    if (!active) return;

    const previouslyFocused = document.activeElement as HTMLElement | null;

    function handleKeyDown(event: KeyboardEvent) {
      const onEscape = onEscapeRef.current;
      if (event.key === "Escape" && onEscape && !disabledRef.current) {
        onEscape();
        return;
      }

      if (event.key !== "Tab" || !containerRef.current) return;

      const focusable = Array.from(
        containerRef.current.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR),
      ).filter((element) => element.offsetParent !== null);
      if (focusable.length === 0) return;

      const first = focusable[0];
      const last = focusable[focusable.length - 1];

      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    }

    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("keydown", handleKeyDown);
      previouslyFocused?.focus?.();
    };
  }, [active, containerRef]);
}
