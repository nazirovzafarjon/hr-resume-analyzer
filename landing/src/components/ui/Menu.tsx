import { useEffect, useId, useRef, useState, type KeyboardEvent, type ReactNode } from "react";

export type MenuOption<T extends string> = {
  value: T;
  label: string;
  icon?: ReactNode;
  meta?: string;
};

type MenuProps<T extends string> = {
  /** Accessible name of the trigger button and the menu. */
  label: string;
  trigger: ReactNode;
  options: MenuOption<T>[];
  value: T;
  onChange: (value: T) => void;
  align?: "start" | "end";
  triggerClassName?: string;
};

/**
 * Small single-choice menu (menu button pattern with `menuitemradio` items).
 * Keyboard: Enter/Space/ArrowDown open it, arrows move, Home/End jump,
 * Escape closes and returns focus to the trigger. Clicking outside closes it.
 */
export default function Menu<T extends string>({
  label,
  trigger,
  options,
  value,
  onChange,
  align = "end",
  triggerClassName = "icon-button",
}: MenuProps<T>) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const buttonRef = useRef<HTMLButtonElement>(null);
  const itemRefs = useRef<(HTMLButtonElement | null)[]>([]);
  const menuId = useId();

  // Focus the checked item once, when the menu opens (not on every re-render).
  const selectedIndex = Math.max(0, options.findIndex((option) => option.value === value));
  const selectedIndexRef = useRef(selectedIndex);
  selectedIndexRef.current = selectedIndex;

  useEffect(() => {
    if (!open) return;
    itemRefs.current[selectedIndexRef.current]?.focus();

    function onPointerDown(event: PointerEvent) {
      if (!rootRef.current?.contains(event.target as Node)) setOpen(false);
    }
    document.addEventListener("pointerdown", onPointerDown);
    return () => document.removeEventListener("pointerdown", onPointerDown);
  }, [open]);

  function close(returnFocus: boolean) {
    setOpen(false);
    if (returnFocus) buttonRef.current?.focus();
  }

  function onMenuKeyDown(event: KeyboardEvent) {
    const items = itemRefs.current.filter(Boolean) as HTMLButtonElement[];
    const index = items.indexOf(document.activeElement as HTMLButtonElement);
    const focusAt = (next: number) => items[(next + items.length) % items.length]?.focus();
    switch (event.key) {
      case "ArrowDown":
        event.preventDefault();
        focusAt(index + 1);
        break;
      case "ArrowUp":
        event.preventDefault();
        focusAt(index - 1);
        break;
      case "Home":
        event.preventDefault();
        focusAt(0);
        break;
      case "End":
        event.preventDefault();
        focusAt(items.length - 1);
        break;
      case "Escape":
        event.preventDefault();
        close(true);
        break;
      case "Tab":
        close(false);
        break;
    }
  }

  return (
    <div className="menu" ref={rootRef}>
      <button
        ref={buttonRef}
        type="button"
        className={triggerClassName}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-controls={open ? menuId : undefined}
        aria-label={label}
        title={label}
        onClick={() => setOpen((current) => !current)}
        onKeyDown={(event) => {
          if (event.key === "ArrowDown" && !open) {
            event.preventDefault();
            setOpen(true);
          }
        }}
      >
        {trigger}
      </button>
      {open && (
        <div
          id={menuId}
          role="menu"
          aria-label={label}
          className={`menu-list menu-list--${align}`}
          onKeyDown={onMenuKeyDown}
        >
          {options.map((option, index) => (
            <button
              key={option.value}
              ref={(node) => {
                itemRefs.current[index] = node;
              }}
              type="button"
              role="menuitemradio"
              aria-checked={option.value === value}
              tabIndex={-1}
              className="menu-item"
              onClick={() => {
                onChange(option.value);
                close(true);
              }}
            >
              {option.icon && <span className="menu-item-icon" aria-hidden="true">{option.icon}</span>}
              <span className="menu-item-label">{option.label}</span>
              {option.meta && <span className="menu-item-meta" aria-hidden="true">{option.meta}</span>}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
