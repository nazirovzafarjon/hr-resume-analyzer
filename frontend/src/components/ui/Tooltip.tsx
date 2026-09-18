import type { ReactNode } from "react";

type TooltipProps = {
  /** Tooltip text. Pass `null` to render children untouched (e.g. expanded rail). */
  label: string | null;
  children: ReactNode;
  /** Place the bubble to the right instead of above (collapsed sidebar rail). */
  side?: "top" | "right";
};

/**
 * Lightweight, CSS-only tooltip: no portal, no positioning library, no timers.
 * Used mainly for icon-only controls and for the collapsed navigation rail,
 * where the label is the only way to identify a destination.
 */
export default function Tooltip({ label, children, side = "top" }: TooltipProps) {
  if (!label) return <>{children}</>;

  return (
    <span className="tooltip-host">
      {children}
      <span
        role="tooltip"
        className={`tooltip-bubble${side === "right" ? " tooltip-bubble--right" : ""}`}
      >
        {label}
      </span>
    </span>
  );
}
