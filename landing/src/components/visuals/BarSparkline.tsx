/**
 * Minimal single-series column chart for the illustrative mockups: one hue,
 * 4px rounded data-ends anchored to the baseline, a recessive baseline rule.
 * Purely decorative — the surrounding figure carries the accessible label.
 */
export default function BarSparkline({ values, highlightLast = true }: { values: number[]; highlightLast?: boolean }) {
  const width = 320;
  const height = 120;
  const gap = 10;
  const barWidth = (width - gap * (values.length - 1)) / values.length;
  const max = Math.max(...values);
  const radius = 4;

  return (
    <svg className="bar-chart" viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none" aria-hidden="true" focusable="false">
      <line x1="0" x2={width} y1={height - 0.5} y2={height - 0.5} className="bar-chart-baseline" />
      {values.map((value, index) => {
        const barHeight = Math.max(radius * 2, (value / max) * (height - 8));
        const x = index * (barWidth + gap);
        const y = height - barHeight;
        const r = radius;
        // Rounded top corners only; the bar sits flat on the baseline.
        const d = `M${x},${height} V${y + r} Q${x},${y} ${x + r},${y} H${x + barWidth - r} Q${x + barWidth},${y} ${x + barWidth},${y + r} V${height} Z`;
        const isLast = index === values.length - 1;
        return <path key={index} d={d} className={highlightLast && isLast ? "bar-chart-bar is-current" : "bar-chart-bar"} />;
      })}
    </svg>
  );
}
