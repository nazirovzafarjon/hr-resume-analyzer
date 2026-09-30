import type { ReactNode } from "react";
import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { useChartPalette, tooltipContentStyle, CHART_ANIMATION_MS } from "./chartTheme";
import ChartFrame from "./ChartFrame";

export type BarDatum = { key: string; label: string; value: number };

type BarComparisonChartProps = {
  title: string;
  subtitle?: string;
  action?: ReactNode;
  data: BarDatum[];
  valueLabel?: string;
  loading?: boolean;
  error?: string | null;
  onRetry?: () => void;
  emptyTitle: string;
  emptyMessage: string;
  errorTitle?: string;
  retryLabel?: string;
  color?: string;
};

/**
 * Horizontal bar comparison — long category labels (job names) stay readable
 * because the bars run left-to-right instead of squeezing labels underneath.
 */
export default function BarComparisonChart({
  title,
  subtitle,
  action,
  data,
  valueLabel = "Count",
  loading,
  error,
  onRetry,
  emptyTitle,
  emptyMessage,
  errorTitle,
  retryLabel,
  color,
}: BarComparisonChartProps) {
  const palette = useChartPalette();
  const sorted = [...data].sort((a, b) => b.value - a.value);
  const isEmpty = sorted.every((d) => d.value === 0);
  const height = Math.max(200, Math.min(sorted.length, 8) * 38 + 40);

  return (
    <ChartFrame
      title={title}
      subtitle={subtitle}
      action={action}
      height={height}
      loading={loading}
      error={error}
      onRetry={onRetry}
      isEmpty={isEmpty}
      emptyTitle={emptyTitle}
      emptyMessage={emptyMessage}
      errorTitle={errorTitle}
      retryLabel={retryLabel}
    >
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={sorted} layout="vertical" margin={{ top: 4, right: 24, left: 0, bottom: 4 }}>
          <CartesianGrid stroke={palette.borderSubtle} horizontal={false} />
          <XAxis
            type="number"
            allowDecimals={false}
            tick={{ fill: palette.textMuted, fontSize: 12 }}
            axisLine={false}
            tickLine={false}
          />
          <YAxis
            type="category"
            dataKey="label"
            width={150}
            tick={{ fill: palette.textSecondary, fontSize: 12 }}
            axisLine={false}
            tickLine={false}
          />
          <Tooltip
            contentStyle={tooltipContentStyle(palette)}
            formatter={(value) => [String(value ?? 0), valueLabel]}
            cursor={{ fill: palette.surfaceSunken }}
          />
          <Bar dataKey="value" radius={[0, 6, 6, 0]} maxBarSize={22} isAnimationActive animationDuration={CHART_ANIMATION_MS}>
            {sorted.map((entry) => (
              <Cell key={entry.key} fill={color ?? palette.primary} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </ChartFrame>
  );
}
