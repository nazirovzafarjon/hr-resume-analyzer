import { useId, type KeyboardEvent, type ReactNode } from "react";

export type TabItem = {
  id: string;
  label: string;
  icon?: ReactNode;
  /** Optional count/label rendered after the title. */
  badge?: ReactNode;
};

type TabsProps = {
  items: TabItem[];
  activeId: string;
  onChange: (id: string) => void;
  ariaLabel: string;
  /** Shared prefix so <TabPanel> can point back at the right tab. */
  idPrefix?: string;
  className?: string;
};

/**
 * Horizontal tab strip with roving arrow-key navigation (WAI-ARIA tabs
 * pattern). Panels live with the caller so a tab can render links or plain
 * sections without this component knowing about routing.
 */
export default function Tabs({
  items,
  activeId,
  onChange,
  ariaLabel,
  idPrefix,
  className,
}: TabsProps) {
  const generated = useId();
  const prefix = idPrefix ?? generated;

  function handleKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    const delta = event.key === "ArrowRight" ? 1 : event.key === "ArrowLeft" ? -1 : 0;
    if (delta === 0) return;

    event.preventDefault();
    const currentIndex = items.findIndex((item) => item.id === activeId);
    const nextIndex = (currentIndex + delta + items.length) % items.length;
    onChange(items[nextIndex].id);
    document.getElementById(`${prefix}-tab-${items[nextIndex].id}`)?.focus();
  }

  return (
    <div
      className={`tabs${className ? ` ${className}` : ""}`}
      role="tablist"
      aria-label={ariaLabel}
      onKeyDown={handleKeyDown}
    >
      {items.map((item) => {
        const selected = item.id === activeId;
        return (
          <button
            key={item.id}
            id={`${prefix}-tab-${item.id}`}
            type="button"
            role="tab"
            aria-selected={selected}
            aria-controls={`${prefix}-panel-${item.id}`}
            tabIndex={selected ? 0 : -1}
            className="tab"
            onClick={() => onChange(item.id)}
          >
            {item.icon}
            {item.label}
            {item.badge}
          </button>
        );
      })}
    </div>
  );
}

/** Companion panel; keeps the aria wiring in one place. */
export function TabPanel({
  id,
  idPrefix,
  activeId,
  children,
}: {
  id: string;
  idPrefix: string;
  activeId: string;
  children: ReactNode;
}) {
  if (id !== activeId) return null;
  return (
    <div
      id={`${idPrefix}-panel-${id}`}
      role="tabpanel"
      aria-labelledby={`${idPrefix}-tab-${id}`}
      className="tab-panel"
    >
      {children}
    </div>
  );
}