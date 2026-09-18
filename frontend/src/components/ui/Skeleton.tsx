import type { CSSProperties } from "react";

type SkeletonProps = {
  /** Any CSS length. Defaults to a full-width 12px line. */
  width?: string | number;
  height?: string | number;
  /** Adds the skeleton-avatar / -title / -block shape modifiers. */
  variant?: "text" | "title" | "avatar" | "block";
  className?: string;
  style?: CSSProperties;
};

/**
 * Shimmering placeholder used while data loads. Rendered as a plain span so it
 * can be dropped inline (next to a label, inside a table cell) without
 * breaking layout or semantics — it is decoration, so it is aria-hidden.
 */
export function Skeleton({
  width,
  height,
  variant = "text",
  className,
  style,
}: SkeletonProps) {
  const classes = ["skeleton", `skeleton-${variant}`, className]
    .filter(Boolean)
    .join(" ");

  return (
    <span
      className={classes}
      aria-hidden="true"
      style={{ width, height, ...style }}
    />
  );
}

/** A paragraph-shaped placeholder. */
export function SkeletonText({ lines = 3, className }: { lines?: number; className?: string }) {
  return (
    <span className={`skeleton-stack${className ? ` ${className}` : ""}`} aria-hidden="true">
      {Array.from({ length: lines }).map((_, index) => (
        <span
          key={index}
          className="skeleton skeleton-text"
          style={index === lines - 1 ? { width: "60%" } : undefined}
        />
      ))}
    </span>
  );
}

/**
 * Table placeholder that mirrors the real table's paddings so the layout does
 * not jump when the data arrives.
 */
export function SkeletonTable({ rows = 5, columns = 4 }: { rows?: number; columns?: number }) {
  return (
    <div className="skeleton-table" aria-hidden="true">
      <div className="skeleton-table-head">
        <Skeleton width="30%" height={10} />
      </div>
      {Array.from({ length: rows }).map((_, rowIndex) => (
        <div key={rowIndex} className="skeleton-table-row">
          {Array.from({ length: columns }).map((_, columnIndex) => (
            <Skeleton
              key={columnIndex}
              height={12}
              width={columnIndex === 0 ? "22%" : columnIndex === columns - 1 ? "10%" : "16%"}
            />
          ))}
        </div>
      ))}
    </div>
  );
}

/** Card grid placeholder for dashboard/analytics style pages. */
export function SkeletonCards({ count = 4 }: { count?: number }) {
  return (
    <div className="stat-grid" aria-hidden="true">
      {Array.from({ length: count }).map((_, index) => (
        <div key={index} className="stat-card">
          <Skeleton width="45%" height={12} />
          <Skeleton width="30%" height={26} style={{ marginTop: "8px" }} />
          <Skeleton width="55%" height={10} style={{ marginTop: "8px" }} />
        </div>
      ))}
    </div>
  );
}
