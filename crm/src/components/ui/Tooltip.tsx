import { useState, type ReactNode } from "react";

type TooltipProps = {
  /** Tooltip text. Pass `null` to render children untouched (e.g. expanded rail). */
  label: string | null;
  children: ReactNode;
  /** Place the bubble to the right instead of above (collapsed sidebar rail). */
  side?: "top" | "right";
};

const RIGHT_GAP = 8;

/**
 * Lightweight tooltip: no portal, no positioning library, no timers.
 * Used mainly for icon-only controls and for the collapsed navigation rail,
 * where the label is the only way to identify a destination.
 *
 * Right-side bubbles live inside the scrollable sidebar nav, whose `overflow`
 * would clip an absolutely positioned bubble. They are therefore placed with
 * `position: fixed` from the host's rect, measured when hover/focus starts.
 */
export default function Tooltip({ label, children, side = "top" }: TooltipProps) {
  const [fixedPos, setFixedPos] = useState<{ top: number; left: number } | null>(null);

  if (!label) return <>{children}</>;

  const measure =
    side === "right"
      ? (event: { currentTarget: HTMLElement }) => {
          const rect = event.currentTarget.getBoundingClientRect();
          setFixedPos({ top: rect.top + rect.height / 2, left: rect.right + RIGHT_GAP });
        }
      : undefined;

  return (
    <span className="tooltip-host" onMouseEnter={measure} onFocus={measure}>
      {children}
      <span
        role="tooltip"
        className={`tooltip-bubble${side === "right" ? " tooltip-bubble--right" : ""}`}
        style={
          side === "right" && fixedPos
            ? { position: "fixed", top: fixedPos.top, left: fixedPos.left }
            : undefined
        }
      >
        {label}
      </span>
    </span>
  );
}
