import { BarChart3, Briefcase, CalendarClock, FileText, LayoutDashboard, Plus, Users } from "lucide-react";
import BarSparkline from "./BarSparkline";
import { useI18n } from "../../i18n";

const NAV_ICONS = [LayoutDashboard, Briefcase, FileText, Users, CalendarClock, BarChart3];
const KPI_VALUES = ["12", "148", "96", "9"];
const WEEKLY_APPLICATIONS = [14, 22, 18, 27, 24, 31, 29, 36];
const MATCHES = [87, 74, 68];
const STATUS_TONE = ["primary", "info", "neutral"] as const;

/**
 * Conceptual preview of the CRM dashboard (sample data only). Built from the
 * same tokens as the real app, so it follows light/dark mode automatically.
 */
export default function DashboardMockup() {
  const { t } = useI18n();
  const m = t.mockup;

  return (
    <figure className="mockup" role="img" aria-label={t.hero.mockupLabel}>
      <div className="mockup-chrome" aria-hidden="true">
        <span className="mockup-dot" />
        <span className="mockup-dot" />
        <span className="mockup-dot" />
        <span className="mockup-address">{t.common.appName} · {m.nav[0]}</span>
      </div>
      <div className="mockup-body" aria-hidden="true">
        <aside className="mockup-sidebar">
          <div className="mockup-brand">
            <span className="logo-mark logo-mark--sm">RA</span>
            <span>{t.common.appName}</span>
          </div>
          <ul>
            {m.nav.map((label, index) => {
              const Icon = NAV_ICONS[index];
              return (
                <li key={label} className={index === 0 ? "is-active" : undefined}>
                  <Icon size={15} />
                  <span>{label}</span>
                </li>
              );
            })}
          </ul>
        </aside>

        <div className="mockup-main">
          <div className="mockup-header">
            <div>
              <p className="mockup-title">{m.title}</p>
              <p className="mockup-subtitle">{m.subtitle}</p>
            </div>
            <span className="mockup-button">
              <Plus size={14} />
              {m.newJob}
            </span>
          </div>

          <div className="mockup-kpis">
            {m.kpis.map((label, index) => (
              <div key={label} className="mockup-kpi">
                <span className="mockup-kpi-label">{label}</span>
                <span className="mockup-kpi-value">{KPI_VALUES[index]}</span>
              </div>
            ))}
          </div>

          <div className="mockup-panels">
            <div className="mockup-panel mockup-panel--chart">
              <p className="mockup-panel-title">{m.chartTitle}</p>
              <BarSparkline values={WEEKLY_APPLICATIONS} />
            </div>
            <div className="mockup-panel">
              <p className="mockup-panel-title">{m.listTitle}</p>
              <ul className="mockup-candidates">
                {m.candidates.map((candidate, index) => (
                  <li key={candidate.name}>
                    <span className="avatar">{candidate.name.charAt(0)}</span>
                    <span className="mockup-candidate-text">
                      <span className="mockup-candidate-name">{candidate.name}</span>
                      <span className="mockup-candidate-role">{candidate.role}</span>
                    </span>
                    <span className="mockup-score">
                      {MATCHES[index]}% <span>{m.match}</span>
                    </span>
                    <span className={`pill pill--${STATUS_TONE[index]}`}>{candidate.status}</span>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      </div>
    </figure>
  );
}
