import type { ReactNode } from "react";
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { useChartPalette, tooltipContentStyle, CHART_ANIMATION_MS } from "./chartTheme";
import ChartFrame from "./ChartFrame";

export type TrendSeries = { key: string; label: string; color?: string };

type LineTrendChartProps = {
  title: string;
  subtitle?: string;
  action?: ReactNode;
  data: Array<Record<string, number | string>>;
  xKey: string;
  series: TrendSeries[];
  formatX?: (value: string) => string;
  loading?: boolean;
  error?: string | null;
  onRetry?: () => void;
  emptyTitle: string;
  emptyMessage: string;
  errorTitle?: string;
  retryLabel?: string;
  height?: number;
};

/** Primary trend visualization: multi-series line chart over time. */
export default function LineTrendChart({
  title,
  subtitle,
  action,
  data,
  xKey,
  series,
  formatX,
  loading,
  error,
  onRetry,
  emptyTitle,
  emptyMessage,
  errorTitle,
  retryLabel,
  height = 300,
}: LineTrendChartProps) {
  const palette = useChartPalette();
  const isEmpty = data.every((point) => series.every((s) => !(Number(point[s.key]) > 0)));

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
        <LineChart data={data} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
          <CartesianGrid stroke={palette.borderSubtle} vertical={false} />
          <XAxis
            dataKey={xKey}
            tickFormatter={formatX}
            tick={{ fill: palette.textMuted, fontSize: 12 }}
            axisLine={{ stroke: palette.border }}
            tickLine={false}
            minTickGap={28}
          />
          <YAxis
            allowDecimals={false}
            tick={{ fill: palette.textMuted, fontSize: 12 }}
            axisLine={false}
            tickLine={false}
            width={30}
          />
          <Tooltip
            contentStyle={tooltipContentStyle(palette)}
            labelFormatter={(value) => (formatX ? formatX(String(value)) : String(value))}
            cursor={{ stroke: palette.border }}
          />
          <Legend
            wrapperStyle={{ fontSize: 12, color: palette.textMuted, paddingTop: 8 }}
            iconType="circle"
            iconSize={8}
          />
          {series.map((s, index) => (
            <Line
              key={s.key}
              type="monotone"
              dataKey={s.key}
              name={s.label}
              stroke={s.color ?? palette.series[index % palette.series.length]}
              strokeWidth={2}
              dot={false}
              activeDot={{ r: 4 }}
              isAnimationActive
              animationDuration={CHART_ANIMATION_MS}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </ChartFrame>
  );
}
