import { Link } from "react-router-dom";
import {
  Bot,
  Briefcase,
  CalendarDays,
  FileText,
  TriangleAlert,
  UserCheck,
  UserRound,
  Users,
} from "lucide-react";
import PageHeader from "../../components/ui/PageHeader";
import PageMeta from "../../components/seo/PageMeta";
import Button from "../../components/ui/Button";
import Card from "../../components/ui/Card";
import EmptyState from "../../components/ui/EmptyState";
import KpiCard from "../../components/dashboard/KpiCard";
import LineTrendChart from "../../components/charts/LineTrendChart";
import AuditActivityList from "../../components/admin/AuditActivityList";
import { SkeletonText } from "../../components/ui/Skeleton";
import { useLanguage } from "../../contexts/LanguageContext";
import { useApiQuery } from "../../hooks/useApiQuery";
import { fetchAdminDashboard } from "../../services/adminService";
import { getErrorMessage } from "../../utils/apiError";
import { formatShortDate } from "./adminFormat";

export default function AdminDashboardPage() {
  const { t } = useLanguage();
  const { data, loading, error, reload } = useApiQuery(fetchAdminDashboard, "dashboard");
  const kpis = data?.kpis;
  const firstLoad = loading && !data;

  if (error && !data) {
    return (
      <div className="page">
        <PageMeta title={t("admin.nav.dashboard")} noindex />
        <PageHeader title={t("admin.dashboard.title")} description={t("admin.dashboard.description")} />
        <EmptyState
          tone="error"
          title={t("errors.loadTitle")}
          message={getErrorMessage(error, t("errors.loadMessage"))}
          action={<Button onClick={reload}>{t("common.retry")}</Button>}
        />
      </div>
    );
  }

  return (
    <div className="page">
      <PageMeta title={t("admin.nav.dashboard")} noindex />
      <PageHeader
        title={t("admin.dashboard.title")}
        description={t("admin.dashboard.description")}
        action={
          <Button variant="secondary" onClick={reload} loading={loading && Boolean(data)}>
            {t("admin.common.refresh")}
          </Button>
        }
      />

      <div className="kpi-grid">
        <KpiCard
          primary
          label={t("admin.dashboard.kpi.users")}
          value={kpis?.users_total ?? 0}
          hint={t("admin.dashboard.kpi.usersHint", {
            active: kpis?.users_active ?? 0,
            inactive: kpis?.users_inactive ?? 0,
          })}
          icon={<Users size={16} />}
          loading={firstLoad}
        />
        <KpiCard
          label={t("admin.dashboard.kpi.admins")}
          value={kpis?.admins ?? 0}
          icon={<UserCheck size={16} />}
          loading={firstLoad}
        />
        <KpiCard
          label={t("admin.dashboard.kpi.jobs")}
          value={kpis?.jobs ?? 0}
          icon={<Briefcase size={16} />}
          loading={firstLoad}
        />
        <KpiCard
          label={t("admin.dashboard.kpi.applications")}
          value={kpis?.applications ?? 0}
          icon={<FileText size={16} />}
          loading={firstLoad}
        />
        <KpiCard
          label={t("admin.dashboard.kpi.candidates")}
          value={kpis?.candidates ?? 0}
          icon={<UserRound size={16} />}
          loading={firstLoad}
        />
        <KpiCard
          label={t("admin.dashboard.kpi.interviews")}
          value={kpis?.interviews ?? 0}
          icon={<CalendarDays size={16} />}
          loading={firstLoad}
        />
        <KpiCard
          label={t("admin.dashboard.kpi.aiAnalyzed")}
          value={kpis?.ai_analyzed ?? 0}
          hint={t("admin.dashboard.kpi.aiFailedHint", { count: kpis?.ai_failed ?? 0 })}
          tone={kpis && kpis.ai_failed > 0 ? "warning" : "default"}
          icon={<Bot size={16} />}
          loading={firstLoad}
        />
        <KpiCard
          label={t("admin.dashboard.kpi.errors")}
          value={kpis?.errors_24h ?? 0}
          hint={t("admin.dashboard.kpi.errorsHint")}
          tone={kpis && kpis.errors_24h > 0 ? "danger" : "success"}
          icon={<TriangleAlert size={16} />}
          loading={firstLoad}
        />
      </div>

      <div className="dashboard-grid dashboard-grid--even">
        <LineTrendChart
          title={t("admin.dashboard.growthTitle")}
          subtitle={t("admin.dashboard.last30Days")}
          data={data?.trend ?? []}
          xKey="date"
          formatX={formatShortDate}
          series={[
            { key: "registrations", label: t("admin.series.registrations") },
            { key: "jobs", label: t("admin.series.jobs") },
          ]}
          loading={firstLoad}
          emptyTitle={t("admin.dashboard.noTrendTitle")}
          emptyMessage={t("admin.dashboard.noTrendMessage")}
        />
        <LineTrendChart
          title={t("admin.dashboard.applicationsTitle")}
          subtitle={t("admin.dashboard.last30Days")}
          data={data?.trend ?? []}
          xKey="date"
          formatX={formatShortDate}
          series={[
            { key: "applications", label: t("admin.series.applications") },
            { key: "ai_completed", label: t("admin.series.aiCompleted") },
            { key: "ai_failed", label: t("admin.series.aiFailed") },
          ]}
          loading={firstLoad}
          emptyTitle={t("admin.dashboard.noTrendTitle")}
          emptyMessage={t("admin.dashboard.noTrendMessage")}
        />
      </div>

      <Card
        title={t("admin.dashboard.recentActivity")}
        subtitle={t("admin.dashboard.recentActivityHint")}
        action={<Link to="/admin/audit-logs">{t("admin.dashboard.viewAuditLog")}</Link>}
      >
        {firstLoad ? (
          <SkeletonText lines={5} />
        ) : (
          <AuditActivityList
            entries={data?.recent_activity ?? []}
            emptyTitle={t("admin.dashboard.noActivityTitle")}
            emptyMessage={t("admin.dashboard.noActivityMessage")}
          />
        )}
      </Card>
    </div>
  );
}
