import type { ReactNode } from "react";
import { ArrowDown, ArrowUp } from "lucide-react";
import { Skeleton } from "../ui/Skeleton";

type Tone = "default" | "primary" | "success" | "info" | "warning" | "danger";

export type KpiDelta = {
  /** Absolute percentage change, always computed from a real previous-period value. */
  value: number;
  direction: "up" | "down" | "flat";
  comparisonLabel: string;
};

type KpiCardProps = {
  label: string;
  value: string | number;
  hint?: string;
  icon?: ReactNode;
  tone?: Tone;
  delta?: KpiDelta;
  /** Larger, bolder treatment for the single most important KPI. */
  primary?: boolean;
  loading?: boolean;
  errorMessage?: string;
};

/** Dashboard KPI card: label, headline number, optional hint and a real (never fabricated) trend delta. */
export default function KpiCard({
  label,
  value,
  hint,
  icon,
  tone = "default",
  delta,
  primary = false,
  loading = false,
  errorMessage,
}: KpiCardProps) {
  const classes = [
    "kpi-card",
    tone !== "default" ? `kpi-card--${tone}` : null,
    primary ? "kpi-card--primary" : null,
  ]
    .filter(Boolean)
    .join(" ");

  if (loading) {
    return (
      <div className={classes} aria-hidden="true">
        <Skeleton width="55%" height={12} />
        <Skeleton width="35%" height={primary ? 34 : 26} style={{ marginTop: "var(--space-sm)" }} />
        <Skeleton width="65%" height={10} style={{ marginTop: "var(--space-xs)" }} />
      </div>
    );
  }

  return (
    <div className={classes}>
      <div className="kpi-card-header">
        <p className="kpi-label">{label}</p>
        {icon && (
          <span className="kpi-icon" aria-hidden="true">
            {icon}
          </span>
        )}
      </div>
      {errorMessage ? (
        <>
          <p className="kpi-value kpi-value--error">—</p>
          <p className="kpi-hint kpi-hint--error">{errorMessage}</p>
        </>
      ) : (
        <>
          <p className="kpi-value">{value}</p>
          {hint && <p className="kpi-hint">{hint}</p>}
          {delta && (
            <span className={`kpi-trend kpi-trend--${delta.direction}`}>
              {delta.direction === "up" && <ArrowUp size={11} />}
              {delta.direction === "down" && <ArrowDown size={11} />}
              {Math.abs(delta.value)}% {delta.comparisonLabel}
            </span>
          )}
        </>
      )}
    </div>
  );
}
