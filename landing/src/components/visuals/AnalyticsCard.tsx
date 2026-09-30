import { useI18n } from "../../i18n";

const KPI_VALUES = [24, 183, 421, 37];
const STAGE_COUNTS = [162, 118, 64, 37];

/** Static analytics preview with demo values — not connected to the backend. */
export default function AnalyticsCard() {
  const { t } = useI18n();
  const c = t.analytics.card;
  const max = Math.max(...STAGE_COUNTS);

  return (
    <div className="analytics-card">
      <div className="analytics-card-head">
        <div>
          <p className="analytics-card-title">{c.title}</p>
          <p className="analytics-card-period">{c.period}</p>
        </div>
        <span className="sample-tag">{t.common.sampleData}</span>
      </div>

      <dl className="analytics-kpis">
        {c.kpis.map((label, index) => (
          <div key={label} className="analytics-kpi">
            <dt>{label}</dt>
            <dd>{KPI_VALUES[index]}</dd>
          </div>
        ))}
      </dl>

      <div className="analytics-pipeline">
        <p className="analytics-card-caption">{c.pipelineTitle}</p>
        <ul>
          {c.stages.map((stage, index) => (
            <li key={stage}>
              <span className="analytics-stage-label">{stage}</span>
              <span className="analytics-stage-track" aria-hidden="true">
                <span
                  className="analytics-stage-bar"
                  style={{ width: `${(STAGE_COUNTS[index] / max) * 100}%` }}
                />
              </span>
              <span className="analytics-stage-value">{STAGE_COUNTS[index]}</span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
