import type { ReactNode } from "react";
import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";
import { useChartPalette, tooltipContentStyle } from "./chartTheme";
import ChartFrame from "./ChartFrame";

export type DonutDatum = { key: string; label: string; value: number; color?: string };

type DonutDistributionChartProps = {
  title: string;
  subtitle?: string;
  action?: ReactNode;
  data: DonutDatum[];
  centerLabel?: string;
  loading?: boolean;
  error?: string | null;
  onRetry?: () => void;
  emptyTitle: string;
  emptyMessage: string;
  errorTitle?: string;
  retryLabel?: string;
};

/** Proportional distribution donut, with a center total and a text legend (name, count, %). */
export default function DonutDistributionChart({
  title,
  subtitle,
  action,
  data,
  centerLabel,
  loading,
  error,
  onRetry,
  emptyTitle,
  emptyMessage,
  errorTitle,
  retryLabel,
}: DonutDistributionChartProps) {
  const palette = useChartPalette();
  const total = data.reduce((sum, d) => sum + d.value, 0);
  const isEmpty = total === 0;

  return (
    <ChartFrame
      title={title}
      subtitle={subtitle}
      action={action}
      height={280}
      loading={loading}
      error={error}
      onRetry={onRetry}
      isEmpty={isEmpty}
      emptyTitle={emptyTitle}
      emptyMessage={emptyMessage}
      errorTitle={errorTitle}
      retryLabel={retryLabel}
    >
      <div className="donut-layout">
        <div className="donut-visual">
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie
                data={data}
                dataKey="value"
                nameKey="label"
                innerRadius="62%"
                outerRadius="94%"
                paddingAngle={data.filter((d) => d.value > 0).length > 1 ? 2 : 0}
                stroke="none"
                isAnimationActive={false}
              >
                {data.map((entry, index) => (
                  <Cell key={entry.key} fill={entry.color ?? palette.series[index % palette.series.length]} />
                ))}
              </Pie>
              <Tooltip
                contentStyle={tooltipContentStyle(palette)}
                formatter={(value, _name, item) => {
                  const numeric = typeof value === "number" ? value : Number(value ?? 0);
                  const label = (item?.payload as DonutDatum | undefined)?.label ?? "";
                  const pct = total ? Math.round((numeric / total) * 100) : 0;
                  return [`${numeric} (${pct}%)`, label];
                }}
              />
            </PieChart>
          </ResponsiveContainer>
          <div className="donut-center" aria-hidden="true">
            <span className="donut-center-value">{total}</span>
            {centerLabel && <span className="donut-center-label">{centerLabel}</span>}
          </div>
        </div>
        <ul className="donut-legend">
          {data.map((entry, index) => {
            const pct = total ? Math.round((entry.value / total) * 100) : 0;
            return (
              <li key={entry.key} className="donut-legend-row">
                <span
                  className="donut-legend-swatch"
                  aria-hidden="true"
                  style={{ backgroundColor: entry.color ?? palette.series[index % palette.series.length] }}
                />
                <span className="donut-legend-label">{entry.label}</span>
                <span className="donut-legend-value">{entry.value}</span>
                <span className="donut-legend-percent">{pct}%</span>
              </li>
            );
          })}
        </ul>
      </div>
    </ChartFrame>
  );
}
