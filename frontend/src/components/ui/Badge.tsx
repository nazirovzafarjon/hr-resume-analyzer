import type { ReactNode } from "react";

export type BadgeTone = "neutral" | "success" | "warning" | "danger" | "info" | "primary";

type BadgeProps = {
  children: ReactNode;
  tone?: BadgeTone;
  /** Small leading dot — pairs the colour with a shape cue. */
  dot?: boolean;
  /** Animates the dot (in-progress states such as "Analyzing"). */
  pulse?: boolean;
  icon?: ReactNode;
  className?: string;
  title?: string;
};

/**
 * The single status-chip primitive. Every status in the product (application
 * status, AI analysis, hiring decision, interview state) renders through this
 * so tones and geometry stay consistent — and because the label is always
 * text, status is never communicated by colour alone.
 */
export default function Badge({
  children,
  tone = "neutral",
  dot = false,
  pulse = false,
  icon,
  className,
  title,
}: BadgeProps) {
  const classes = ["badge", `badge--${tone}`, className].filter(Boolean).join(" ");

  return (
    <span className={classes} title={title}>
      {dot && (
        <span
          className={`badge-dot${pulse ? " badge-dot--pulse" : ""}`}
          aria-hidden="true"
        />
      )}
      {icon && <span aria-hidden="true">{icon}</span>}
      {children}
    </span>
  );
}
