import {
  cloneElement,
  isValidElement,
  useCallback,
  useEffect,
  useId,
  useRef,
  useState,
  type ReactElement,
  type ReactNode,
} from "react";

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

/**
 * Accessible dropdown menu used for the profile menu, theme picker, language
 * picker and table row actions.
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
  const containerRef = useRef<HTMLDivElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);
  const id = useId();

  const close = useCallback(() => setOpen(false), []);

  useEffect(() => {
    if (!open) return;

    function handlePointerDown(event: MouseEvent) {
      if (!containerRef.current?.contains(event.target as Node)) close();
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

    document.addEventListener("mousedown", handlePointerDown);
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("mousedown", handlePointerDown);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [open, close]);

  const triggerElement = trigger({ open, toggle: () => setOpen((value) => !value), id });

  return (
    <div
      className={`dropdown${className ? ` ${className}` : ""}`}
      ref={containerRef}
      onClick={() => {
        if (open && closeOnClick) close();
      }}
    >
      {isValidElement(triggerElement)
        ? cloneElement(triggerElement as ReactElement<Record<string, unknown>>, {
            "aria-expanded": open,
            "aria-haspopup": "menu",
            "aria-controls": open ? `${id}-menu` : undefined,
          })
        : triggerElement}

      {open && (
        <div
          id={`${id}-menu`}
          ref={menuRef}
          className={`dropdown-menu dropdown-menu--${align}`}
          role="menu"
        >
          {children}
        </div>
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
