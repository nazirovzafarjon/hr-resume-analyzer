import {
  cloneElement,
  isValidElement,
  useCallback,
  useEffect,
  useId,
  useLayoutEffect,
  useRef,
  useState,
  type ReactElement,
  type ReactNode,
} from "react";
import { createPortal } from "react-dom";

type DropdownProps = {
  /** The clickable trigger. Receives aria-expanded/aria-haspopup props. */
  trigger: (props: {
    open: boolean;
    toggle: () => void;
    id: string;
  }) => ReactElement;
  children: ReactNode;
  /** Align the menu to the left edge of the trigger instead of the right. */
  align?: "left" | "right";
  /** Close the menu after a click inside (menus of actions should). */
  closeOnClick?: boolean;
  className?: string;
};

type MenuPosition = { top: number; left: number };

const MENU_GAP = 4;
const VIEWPORT_MARGIN = 8;

/**
 * Accessible dropdown menu used for the profile menu, theme picker, language
 * picker and table row actions.
 *
 * The menu renders through a portal into document.body, positioned with
 * `position: fixed` from the trigger's own bounding rect. This keeps it from
 * being clipped by any ancestor with `overflow` set (e.g. a scrollable table
 * wrapper) and lets it flip above the trigger when there isn't enough room
 * below in the viewport.
 *
 * Handles what is easy to get wrong: click-outside, Escape, arrow-key roving
 * focus between items (role="menu"/"menuitem"), and returning focus to the
 * trigger when the menu closes.
 */
export default function Dropdown({
  trigger,
  children,
  align = "right",
  closeOnClick = true,
  className,
}: DropdownProps) {
  const [open, setOpen] = useState(false);
  const [position, setPosition] = useState<MenuPosition | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);
  const id = useId();

  const close = useCallback(() => setOpen(false), []);

  const updatePosition = useCallback(() => {
    const triggerEl = containerRef.current?.querySelector<HTMLElement>(
      "[aria-haspopup='menu']",
    );
    const menuEl = menuRef.current;
    if (!triggerEl || !menuEl) return;

    const triggerRect = triggerEl.getBoundingClientRect();
    const menuHeight = menuEl.offsetHeight;
    const menuWidth = menuEl.offsetWidth;

    const spaceBelow = window.innerHeight - triggerRect.bottom;
    const spaceAbove = triggerRect.top;
    const openUpward =
      spaceBelow < menuHeight + MENU_GAP && spaceAbove > spaceBelow;

    const top = openUpward
      ? Math.max(VIEWPORT_MARGIN, triggerRect.top - menuHeight - MENU_GAP)
      : triggerRect.bottom + MENU_GAP;

    const rawLeft =
      align === "right" ? triggerRect.right - menuWidth : triggerRect.left;
    const maxLeft = window.innerWidth - menuWidth - VIEWPORT_MARGIN;
    const left = Math.min(Math.max(VIEWPORT_MARGIN, rawLeft), Math.max(VIEWPORT_MARGIN, maxLeft));

    setPosition({ top, left });
  }, [align]);

  // Measure and place the menu after it mounts (hidden) so sizing is correct
  // before it becomes visible - avoids a flash at the wrong position.
  useLayoutEffect(() => {
    if (!open) {
      setPosition(null);
      return;
    }
    updatePosition();
  }, [open, updatePosition]);

  useEffect(() => {
    if (!open) return;

    function handlePointerDown(event: MouseEvent) {
      const target = event.target as Node;
      if (containerRef.current?.contains(target)) return;
      if (menuRef.current?.contains(target)) return;
      close();
    }

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        event.stopPropagation();
        close();
        // Hand focus back to the trigger so keyboard users do not get lost.
        containerRef.current
          ?.querySelector<HTMLElement>("[aria-haspopup='menu']")
          ?.focus();
        return;
      }

      if (event.key !== "ArrowDown" && event.key !== "ArrowUp") return;

      const items = Array.from(
        menuRef.current?.querySelectorAll<HTMLElement>(
          "[role='menuitem'], [role='menuitemradio']",
        ) ?? [],
      );
      if (items.length === 0) return;

      event.preventDefault();
      const currentIndex = items.findIndex((item) => item === document.activeElement);
      const delta = event.key === "ArrowDown" ? 1 : -1;
      const nextIndex = (currentIndex + delta + items.length) % items.length;
      items[nextIndex].focus();
    }

    // Any ancestor scroll invalidates the trigger's rect - close rather than
    // chase a moving target with a repositioning loop.
    function handleScroll() {
      close();
    }

    document.addEventListener("mousedown", handlePointerDown);
    document.addEventListener("keydown", handleKeyDown);
    window.addEventListener("resize", updatePosition);
    document.addEventListener("scroll", handleScroll, true);
    return () => {
      document.removeEventListener("mousedown", handlePointerDown);
      document.removeEventListener("keydown", handleKeyDown);
      window.removeEventListener("resize", updatePosition);
      document.removeEventListener("scroll", handleScroll, true);
    };
  }, [open, close, updatePosition]);

  const triggerElement = trigger({ open, toggle: () => setOpen((value) => !value), id });

  return (
    <div className={`dropdown${className ? ` ${className}` : ""}`} ref={containerRef}>
      {isValidElement(triggerElement)
        ? cloneElement(triggerElement as ReactElement<Record<string, unknown>>, {
            "aria-expanded": open,
            "aria-haspopup": "menu",
            "aria-controls": open ? `${id}-menu` : undefined,
          })
        : triggerElement}

      {open &&
        createPortal(
          <div
            id={`${id}-menu`}
            ref={menuRef}
            className="dropdown-menu dropdown-menu--portal"
            role="menu"
            style={{
              position: "fixed",
              top: position?.top ?? -9999,
              left: position?.left ?? -9999,
              right: "auto",
              visibility: position ? "visible" : "hidden",
            }}
            onClick={() => {
              if (closeOnClick) close();
            }}
          >
            {children}
          </div>,
          document.body,
        )}
    </div>
  );
}

type DropdownItemProps = {
  children: ReactNode;
  icon?: ReactNode;
  onClick?: () => void;
  /** Use "menuitemradio" semantics for selectable options (theme, language). */
  role?: "menuitem" | "menuitemradio";
  checked?: boolean;
  danger?: boolean;
  meta?: string;
  /** Render as a link item (React Router <Link> passes its own props). */
  as?: "button";
  disabled?: boolean;
};

/** A single row inside <Dropdown>. */
export function DropdownItem({
  children,
  icon,
  onClick,
  role = "menuitem",
  checked,
  danger = false,
  meta,
  disabled = false,
}: DropdownItemProps) {
  return (
    <button
      type="button"
      role={role}
      aria-checked={role === "menuitemradio" ? Boolean(checked) : undefined}
      className={`dropdown-item${danger ? " dropdown-item--danger" : ""}`}
      onClick={onClick}
      disabled={disabled}
      tabIndex={-1}
    >
      {icon && <span className="dropdown-item-icon">{icon}</span>}
      <span className="dropdown-item-label">{children}</span>
      {meta && <span className="dropdown-item-meta">{meta}</span>}
    </button>
  );
}

export function DropdownSeparator() {
  return <div className="dropdown-separator" role="separator" />;
}

export function DropdownLabel({ children }: { children: ReactNode }) {
  return <div className="dropdown-label">{children}</div>;
}
