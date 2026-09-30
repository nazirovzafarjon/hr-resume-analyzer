import { useCallback, useMemo } from "react";
import { Link } from "react-router-dom";
import PageHeader from "../../components/ui/PageHeader";
import PageMeta from "../../components/seo/PageMeta";
import Badge from "../../components/ui/Badge";
import Button from "../../components/ui/Button";
import Card from "../../components/ui/Card";
import EmptyState from "../../components/ui/EmptyState";
import FilterBar from "../../components/ui/FilterBar";
import StatCard from "../../components/ui/StatCard";
import Table, { type TableColumn } from "../../components/ui/Table";
import { SkeletonCards } from "../../components/ui/Skeleton";
import BarComparisonChart from "../../components/charts/BarComparisonChart";
import ServerTable from "../../components/admin/ServerTable";
import { RunStatusBadge, formatScore } from "../../components/admin/badges";
import { DateRangeFields, ToolbarSelect } from "../../components/admin/filters";
import { useLanguage } from "../../contexts/LanguageContext";
import { useApiQuery } from "../../hooks/useApiQuery";
import { useUrlFilters } from "../../hooks/useUrlFilters";
import { fetchAIOverview, fetchAIRuns } from "../../services/adminService";
import { getErrorMessage } from "../../utils/apiError";
import { formatDateTime } from "../../utils/date";
import { translateOr } from "../../utils/statusLabels";
import type { AIOverview, AIRunRow } from "../../types/admin";
import { formatDuration } from "./adminFormat";

const DEFAULTS = { status: "", kind: "", error_category: "", date_from: "", date_to: "" };
const PAGE_SIZE = 25;
/** Below this many finished attempts a success rate is noise, so it is not shown. */
const MIN_RATE_SAMPLE = 5;
const CATEGORIES = [
  "rate_limited",
  "auth",
  "unavailable",
  "invalid_response",
  "bad_request",
  "not_found",
  "validation",
  "unexpected",
];

type Batch = AIOverview["recent_batches"][number];

export default function AdminAIAnalysisPage() {
  const { t } = useLanguage();
  const overview = useApiQuery(fetchAIOverview, "ai-overview");
  const { values, page, setFilters, setPage, clear, active } = useUrlFilters(DEFAULTS);
  const params = { ...values, page, limit: PAGE_SIZE };
  const runs = useApiQuery(() => fetchAIRuns(params), JSON.stringify(params));
  const data = overview.data;
  const finishedRuns = data ? data.runs_all_time.completed + data.runs_all_time.failed : 0;
  const rateShown = data?.runs_all_time.success_rate != null && finishedRuns >= MIN_RATE_SAMPLE;

  const categoryLabel = useCallback(
    (key: string) => translateOr(t, `admin.ai.categories.${key}`, key),
    [t],
  );

  const runColumns = useMemo<TableColumn<AIRunRow>[]>(
    () => [
      {
        header: t("admin.ai.time"),
        render: (row) => <span className="table-muted">{formatDateTime(row.created_at)}</span>,
      },
      {
        header: t("admin.ai.outcome"),
        render: (row) => (
          <div>
            <RunStatusBadge status={row.status} />
            {row.error_category && (
              <div className="table-secondary">
                {categoryLabel(row.error_category)}
                {row.http_status ? ` · HTTP ${row.http_status}` : ""}
              </div>
            )}
          </div>
        ),
      },
      {
        header: t("admin.ai.target"),
        render: (row) => (
          <div>
            {row.application_id ? (
              <Link className="table-primary" to={`/admin/applications/${row.application_id}`}>
                {t("admin.ai.kind.application")} #{row.application_id}
              </Link>
            ) : (
              <span className="table-primary">{t(`admin.ai.kind.${row.kind}`)}</span>
            )}
            <div className="table-secondary">
              {[row.position, row.company_name].filter(Boolean).join(" · ") || row.owner_email || "—"}
            </div>
          </div>
        ),
      },
      {
        header: t("admin.ai.provider"),
        hideOnMobile: true,
        render: (row) => (
          <div>
            <div>{row.provider ?? "—"}</div>
            <div className="table-secondary">
              {row.model ?? ""}
              {row.source === "custom" ? ` · ${t("admin.ai.customKey")}` : ""}
            </div>
          </div>
        ),
      },
      {
        header: t("admin.ai.duration"),
        className: "table-number",
        hideOnMobile: true,
        render: (row) => formatDuration(row.duration_ms),
      },
      {
        header: t("admin.ai.detail"),
        hideOnMobile: true,
        render: (row) =>
          row.status === "completed" ? (
            <span className="table-muted">{formatScore(row.score)}</span>
          ) : (
            <span className="table-muted admin-truncate" title={row.error_message ?? undefined}>
              {row.error_message ?? "—"}
            </span>
          ),
      },
    ],
    [t, categoryLabel],
  );

  const batchColumns = useMemo<TableColumn<Batch>[]>(
    () => [
      { header: "#", render: (batch) => batch.id },
      { header: t("admin.ai.batchOwner"), render: (batch) => batch.owner_email ?? "—" },
      {
        header: t("admin.ai.batchStatus"),
        render: (batch) => (
          <Badge
            tone={batch.status === "completed" ? "success" : batch.status === "failed" ? "danger" : batch.status === "cancelled" ? "neutral" : "warning"}
            dot
            pulse={batch.status === "running"}
          >
            {translateOr(t, `admin.ai.batchStatuses.${batch.status}`, batch.status)}
          </Badge>
        ),
      },
      {
        header: t("admin.ai.batchProgress"),
        render: (batch) =>
          t("admin.ai.batchProgressValue", {
            done: batch.successful,
            failed: batch.failed,
            skipped: batch.skipped,
            total: batch.total,
          }),
      },
      {
        header: t("admin.ai.time"),
        hideOnMobile: true,
        render: (batch) => <span className="table-muted">{formatDateTime(batch.created_at)}</span>,
      },
    ],
    [t],
  );

  return (
    <div className="page">
      <PageMeta title={t("admin.nav.aiAnalysis")} noindex />
      <PageHeader
        title={t("admin.ai.title")}
        description={t("admin.ai.description")}
        action={
          <Button variant="secondary" onClick={() => { overview.reload(); runs.reload(); }}>
            {t("admin.common.refresh")}
          </Button>
        }
      />

      {overview.error && !data ? (
        <EmptyState
          tone="error"
          title={t("errors.loadTitle")}
          message={getErrorMessage(overview.error, t("errors.loadMessage"))}
          action={<Button onClick={overview.reload}>{t("common.retry")}</Button>}
        />
      ) : !data ? (
        <SkeletonCards count={4} />
      ) : (
        <>
          <div className="stat-grid">
            <StatCard
              label={t("admin.ai.analyzedApplications")}
              value={data.analysis_status.find((item) => item.key === "completed")?.count ?? 0}
              hint={t("admin.ai.analyzedHint")}
            />
            <StatCard
              label={t("admin.ai.successRate")}
              value={rateShown ? `${data.runs_all_time.success_rate}%` : "—"}
              hint={
                rateShown
                  ? t("admin.ai.runsHint", {
                      completed: data.runs_all_time.completed,
                      failed: data.runs_all_time.failed,
                    })
                  : t("admin.ai.tooFewRuns", { count: finishedRuns, min: MIN_RATE_SAMPLE })
              }
              tone={
                !rateShown
                  ? "default"
                  : (data.runs_all_time.success_rate ?? 0) >= 90
                    ? "success"
                    : "warning"
              }
            />
            <StatCard
              label={t("admin.ai.failed24h")}
              value={data.runs_24h.failed}
              hint={t("admin.ai.attempts24h", { count: data.runs_24h.total })}
              tone={data.runs_24h.failed > 0 ? "danger" : "default"}
            />
            <StatCard
              label={t("admin.ai.avgDuration")}
              value={formatDuration(data.runs_all_time.avg_duration_ms)}
              hint={t("admin.ai.avgScore", { score: formatScore(data.avg_score) })}
            />
          </div>

          <p className="admin-note">
            {t("admin.ai.providerNote", {
              provider: data.platform_provider.provider,
              model: data.platform_provider.model ?? t("admin.ai.notSet"),
              users: data.platform_provider.custom_provider_users,
            })}
            {!data.platform_provider.api_key_configured && ` ${t("admin.ai.noPlatformKey")}`}
          </p>

          <div className="dashboard-grid dashboard-grid--even">
            <BarComparisonChart
              title={t("admin.ai.statusChart")}
              subtitle={t("admin.ai.statusChartHint")}
              data={data.analysis_status.map((item) => ({
                key: item.key,
                label: translateOr(t, `statusMeta.analysis.${item.key}`, item.key),
                value: item.count,
              }))}
              valueLabel={t("admin.series.applications")}
              emptyTitle={t("admin.ai.noDataTitle")}
              emptyMessage={t("admin.ai.noDataMessage")}
            />
            <BarComparisonChart
              title={t("admin.ai.failuresChart")}
              subtitle={t("admin.ai.failuresChartHint")}
              data={data.failure_categories.map((item) => ({
                key: item.key,
                label: categoryLabel(item.key),
                value: item.count,
              }))}
              valueLabel={t("admin.ai.failures")}
              emptyTitle={t("admin.ai.noFailuresTitle")}
              emptyMessage={t("admin.ai.noFailuresMessage")}
            />
          </div>

          <Card title={t("admin.ai.batchesTitle")} subtitle={t("admin.ai.batchesHint")} flush>
            <Table
              columns={batchColumns}
              rows={data.recent_batches}
              rowKey={(batch) => batch.id}
              caption={t("admin.ai.batchesTitle")}
              emptyState={<EmptyState title={t("admin.ai.noBatchesTitle")} message={t("admin.ai.noBatchesMessage")} />}
            />
          </Card>
        </>
      )}

      <Card title={t("admin.ai.runsTitle")} subtitle={t("admin.ai.runsSubtitle")} flush>
        <FilterBar active={active} onClear={clear}>
          <ToolbarSelect
            label={t("admin.ai.outcome")}
            value={values.status}
            onChange={(status) => setFilters({ status })}
            allLabel={t("labels.all")}
            options={[
              { value: "completed", label: t("admin.ai.runStatus.completed") },
              { value: "failed", label: t("admin.ai.runStatus.failed") },
            ]}
          />
          <ToolbarSelect
            label={t("admin.ai.type")}
            value={values.kind}
            onChange={(kind) => setFilters({ kind })}
            allLabel={t("labels.all")}
            options={[
              { value: "application", label: t("admin.ai.kind.application") },
              { value: "vacancy", label: t("admin.ai.kind.vacancy") },
            ]}
          />
          <ToolbarSelect
            label={t("admin.ai.category")}
            value={values.error_category}
            onChange={(error_category) => setFilters({ error_category })}
            allLabel={t("labels.all")}
            options={CATEGORIES.map((value) => ({ value, label: categoryLabel(value) }))}
          />
          <DateRangeFields from={values.date_from} to={values.date_to} onChange={setFilters} />
        </FilterBar>
        <ServerTable
          columns={runColumns}
          data={runs.data}
          loading={runs.loading}
          error={runs.error}
          onRetry={runs.reload}
          rowKey={(row) => row.id}
          caption={t("admin.ai.runsTitle")}
          onPageChange={setPage}
          filtered={active}
          onClearFilters={clear}
          emptyTitle={t("admin.ai.noRunsTitle")}
          emptyMessage={t("admin.ai.noRunsMessage")}
        />
      </Card>
    </div>
  );
}
