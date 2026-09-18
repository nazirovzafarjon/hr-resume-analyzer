type StatCardProps = {
  label: string;
  value: string | number;
  hint?: string;
  tone?: "default" | "success" | "info" | "warning" | "danger";
  /** Optional leading icon for visual grouping. */
  icon?: React.ReactNode;
};

/** Small KPI card used on Applications / Interviews / Analytics pages. */
export default function StatCard({ label, value, hint, tone = "default", icon }: StatCardProps) {
  return (
    <div
      className={`stat-card${tone !== "default" ? ` stat-card--${tone}` : ""}`}
    >
      <p className="stat-label">
        {icon && (
          <span
            aria-hidden="true"
            style={{ display: "inline-flex", verticalAlign: "-2px", marginRight: "6px" }}
          >
            {icon}
          </span>
        )}
        {label}
      </p>
      <p className="stat-value">{value}</p>
      {hint && <p className="stat-hint">{hint}</p>}
    </div>
  );
}
