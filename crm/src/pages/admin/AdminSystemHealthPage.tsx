import { useEffect } from "react";
import { Activity, Bot, Database, HardDrive, Mail, Server } from "lucide-react";
import PageHeader from "../../components/ui/PageHeader";
import PageMeta from "../../components/seo/PageMeta";
import Button from "../../components/ui/Button";
import Card from "../../components/ui/Card";
import EmptyState from "../../components/ui/EmptyState";
import { SkeletonCards } from "../../components/ui/Skeleton";
import { HealthBadge } from "../../components/admin/badges";
import { useLanguage } from "../../contexts/LanguageContext";
import { useApiQuery } from "../../hooks/useApiQuery";
import { fetchSystemHealth } from "../../services/adminService";
import { getErrorMessage } from "../../utils/apiError";
import { formatDateTime } from "../../utils/date";

const ICONS = {
  api: Server,
  database: Database,
  ai_provider: Bot,
  email: Mail,
  storage: HardDrive,
  workers: Activity,
} as const;

/** Refresh interval while the page is visible (checks are cheap by design). */
const AUTO_REFRESH_MS = 60_000;

export default function AdminSystemHealthPage() {
  const { t } = useLanguage();
  const { data, loading, error, reload } = useApiQuery(fetchSystemHealth, "health");

  // Poll only while the tab is visible, and re-check when it becomes visible
  // again, so a forgotten background tab never keeps hitting the API.
  useEffect(() => {
    const timer = window.setInterval(() => {
      if (document.visibilityState === "visible") reload();
    }, AUTO_REFRESH_MS);
    function onVisible() {
      if (document.visibilityState === "visible") reload();
    }
    document.addEventListener("visibilitychange", onVisible);
    return () => {
      window.clearInterval(timer);
      document.removeEventListener("visibilitychange", onVisible);
    };
  }, [reload]);

  const metricLabel = (key: string) => t(`admin.health.metrics.${key}`);
  const metricValue = (value: string | number | boolean | null) =>
    value === null ? "—" : typeof value === "boolean" ? (value ? t("common.yes") : t("common.no")) : String(value);

  return (
    <div className="page">
      <PageMeta title={t("admin.nav.systemHealth")} noindex />
      <PageHeader
        title={t("admin.health.title")}
        description={t("admin.health.description")}
        action={
          <Button variant="secondary" onClick={reload} loading={loading && Boolean(data)}>
            {t("admin.health.checkNow")}
          </Button>
        }
      />

      {error && !data ? (
        // The admin endpoint itself needs the database for authentication, so
        // a full outage shows up here as a failed request.
        <EmptyState
          tone="error"
          title={t("admin.health.unreachableTitle")}
          message={getErrorMessage(error, t("admin.health.unreachableMessage"))}
          action={<Button onClick={reload}>{t("common.retry")}</Button>}
        />
      ) : !data ? (
        <SkeletonCards count={6} />
      ) : (
        <>
          <div className={`health-summary health-summary--${data.status}`} role="status" aria-live="polite">
            <HealthBadge status={data.status} />
            <span>{t(`admin.health.overall.${data.status}`)}</span>
            <span className="table-secondary">
              {t("admin.health.checkedAt", { time: formatDateTime(data.checked_at) })}
            </span>
          </div>

          <div className="health-grid">
            {data.components.map((component) => {
              const Icon = ICONS[component.key as keyof typeof ICONS] ?? Server;
              const metrics = Object.entries(component.metrics);
              return (
                <Card
                  key={component.key}
                  title={t(`admin.health.components.${component.key}`)}
                  icon={<Icon size={16} />}
                  action={<HealthBadge status={component.status} />}
                >
                  <p className="table-muted">{component.detail}</p>
                  {(component.latency_ms !== null || metrics.length > 0) && (
                    <dl className="detail-list health-metrics">
                      {component.latency_ms !== null && (
                        <>
                          <dt>{t("admin.health.latency")}</dt>
                          <dd>{component.latency_ms} ms</dd>
                        </>
                      )}
                      {metrics.map(([key, value]) => (
                        <div key={key} className="detail-list-row">
                          <dt>{metricLabel(key)}</dt>
                          <dd>{metricValue(value)}</dd>
                        </div>
                      ))}
                    </dl>
                  )}
                </Card>
              );
            })}
          </div>
        </>
      )}
    </div>
  );
}
