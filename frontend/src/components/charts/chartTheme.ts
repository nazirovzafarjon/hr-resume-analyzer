import { useMemo, type CSSProperties } from "react";
import { useTheme } from "../../contexts/ThemeContext";

/**
 * Chart color/typography palette, read live from the design-system CSS custom
 * properties (index.css) so charts never hardcode hex values and automatically
 * track light/dark theme changes.
 */
export type ChartPalette = {
  primary: string;
  success: string;
  warning: string;
  error: string;
  info: string;
  neutral: string;
  text: string;
  textSecondary: string;
  textMuted: string;
  textSubtle: string;
  border: string;
  borderSubtle: string;
  surface: string;
  surfaceRaised: string;
  surfaceSunken: string;
  /** Ordered palette for multi-series charts (line series, donut slices, bars). */
  series: string[];
};

function readVar(name: string, fallback: string): string {
  if (typeof document === "undefined") return fallback;
  const value = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  return value || fallback;
}

function buildPalette(): ChartPalette {
  const primary = readVar("--color-primary", "#f97316");
  const success = readVar("--color-success", "#16a34a");
  const warning = readVar("--color-warning", "#d97706");
  const error = readVar("--color-error", "#dc2626");
  const info = readVar("--color-info", "#0284c7");
  const neutral = readVar("--color-neutral", "#52525b");

  return {
    primary,
    success,
    warning,
    error,
    info,
    neutral,
    text: readVar("--color-text", "#18181b"),
    textSecondary: readVar("--color-text-secondary", "#3f3f46"),
    textMuted: readVar("--color-text-muted", "#71717a"),
    textSubtle: readVar("--color-text-subtle", "#a1a1aa"),
    border: readVar("--color-border", "#e4e4e7"),
    borderSubtle: readVar("--color-border-subtle", "#f1f1f2"),
    surface: readVar("--color-surface", "#ffffff"),
    surfaceRaised: readVar("--color-surface-raised", "#ffffff"),
    surfaceSunken: readVar("--color-surface-sunken", "#f5f5f4"),
    series: [primary, info, success, warning, error, neutral],
  };
}

/** Reads the current theme's chart colors; recomputed whenever the resolved theme flips. */
export function useChartPalette(): ChartPalette {
  const { resolvedTheme } = useTheme();
  return useMemo(() => buildPalette(), [resolvedTheme]);
}

/** Shared Recharts tooltip container style, matching the app's dropdown surface. */
export function tooltipContentStyle(palette: ChartPalette): CSSProperties {
  return {
    background: palette.surfaceRaised,
    border: `1px solid ${palette.border}`,
    borderRadius: 8,
    boxShadow: "var(--shadow-dropdown)",
    fontSize: 13,
    fontFamily: "var(--font-sans)",
    color: palette.text,
    padding: "8px 12px",
  };
}

export const CHART_ANIMATION_MS = 200;
