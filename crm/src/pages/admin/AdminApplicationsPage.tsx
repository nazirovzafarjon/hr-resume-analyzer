import { useCallback, useMemo } from "react";
import { Link } from "react-router-dom";
import { X } from "lucide-react";
import PageHeader from "../../components/ui/PageHeader";
import PageMeta from "../../components/seo/PageMeta";
import Card from "../../components/ui/Card";
import FilterBar from "../../components/ui/FilterBar";
import StatCard from "../../components/ui/StatCard";
import StatusBadge from "../../components/ui/StatusBadge";
import { SkeletonCards } from "../../components/ui/Skeleton";
import { AnalysisStatusBadge, ApplicationStatusBadge } from "../../components/ui/ApplicationStatusBadge";
import ServerTable from "../../components/admin/ServerTable";
import { formatScore } from "../../components/admin/badges";
import {
  CompanySelect,
  DateRangeFields,
  OwnerSelect,
  ToolbarSelect,
  nextSort,
  useSearchInput,
} from "../../components/admin/filters";
import type { TableColumn } from "../../components/ui/Table";
import { useLanguage } from "../../contexts/LanguageContext";
import { useApiQuery } from "../../hooks/useApiQuery";
import { useUrlFilters } from "../../hooks/useUrlFilters";
import { fetchAdminApplications, fetchAdminCandidates } from "../../services/adminService";
import { formatDate } from "../../utils/date";
import { translateOr } from "../../utils/statusLabels";
import type { AdminWorkerRow } from "../../types/admin";

const APPLICATION_STATUSES = ["new", "reviewing", "shortlisted", "interview", "rejected", "withdrawn"];
const HIRING_STATUSES = ["strong_hire", "hire", "weak_hire", "do_not_hire"];
const INTERVIEW_STATUSES = ["in_process", "completed", "not_completed"];
const ANALYSIS_FILTERS = ["analyzed", "not_analyzed", "analyzing", "failed"];
const SCORE_RANGES: Record<string, [number, number]> = {
  "90-100": [90, 100],
  "75-89": [75, 89.99],
  "50-74": [50, 74.99],
  "0-49": [0, 49.99],
};

const APPLICATION_DEFAULTS = {
  q: "",
  owner_id: "",
  company: "",
  job_id: "",
  analysis: "",
  application_status: "",
  hiring_status: "",
  interview_status: "",
  score: "",
  date_from: "",
  date_to: "",
  sort: "submitted_at",
  order: "desc",
};
const CANDIDATE_DEFAULTS = { ...APPLICATION_DEFAULTS, sort: "candidate_at" };

const PAGE_SIZE = 25;

/**
 * Platform-wide applications, or (mode="candidates") only those moved into
 * the hiring pipeline. Both are `workers` rows on the backend.
 */
export default function AdminApplicationsPage({ mode }: { mode: "applications" | "candidates" }) {
  const { t } = useLanguage();
  const candidates = mode === "candidates";
  const { values, page, setFilters, setPage, clear, active } = useUrlFilters(
    candidates ? CANDIDATE_DEFAULTS : APPLICATION_DEFAULTS,
  );
  const commitSearch = useCallback((q: string) => setFilters({ q }), [setFilters]);
  const [search, setSearch] = useSearchInput(values.q, commitSearch);

  const { score, ...rest } = values;
  const [scoreMin, scoreMax] = SCORE_RANGES[score] ?? [undefined, undefined];
  const params = { ...rest, score_min: scoreMin, score_max: scoreMax, page, limit: PAGE_SIZE };
  const fetcher = candidates ? fetchAdminCandidates : fetchAdminApplications;
  const query = useApiQuery(() => fetcher(params), `${mode}:${JSON.stringify(params)}`);
  const summary = query.data?.summary;
  const detailBase = candidates ? "/admin/candidates" : "/admin/applications";

  const statusLabel = useCallback(
    (group: string, value: string) => translateOr(t, `statusMeta.${group}.${value}`, value),
    [t],
  );

  const columns = useMemo<TableColumn<AdminWorkerRow>[]>(
    () => [
      {
        header: t("admin.applications.candidate"),
        sortKey: "name",
        render: (row) => (
          <div>
            <Link className="table-primary" to={`${detailBase}/${row.id}`}>
              {row.name}
            </Link>
            <div className="table-secondary">{row.email}</div>
          </div>
        ),
      },
      {
        header: t("admin.applications.job"),
        render: (row) => (
          <div>
            <Link className="table-primary" to={`/admin/jobs?job=${row.job_id}`}>
              {row.position}
            </Link>
            <div className="table-secondary">{row.company_name}</div>
          </div>
        ),
      },
      {
        header: t("admin.applications.owner"),
        hideOnMobile: true,
        render: (row) => (
          <Link className="table-muted" to={`/admin/users/${row.owner_id}`}>
            {row.owner_email}
          </Link>
        ),
      },
      {
        header: t("admin.applications.aiScore"),
        sortKey: "ai_score",
        className: "table-number",
        render: (row) => (
          <span title={row.ai_recommendation ? t("admin.applications.aiSuggests", {
            value: statusLabel("hiring", row.ai_recommendation),
          }) : undefined}>
            {formatScore(row.ai_score)}
          </span>
        ),
      },
      candidates
        ? {
            header: t("admin.applications.hiringStatus"),
            render: (row) => <StatusBadge kind="hiring" value={row.hiring_status} />,
          }
        : {
            header: t("admin.applications.aiStatus"),
            render: (row) => <AnalysisStatusBadge value={row.analysis_status} />,
          },
      candidates
        ? {
            header: t("admin.applications.interviewStatus"),
            render: (row) => <StatusBadge kind="interview" value={row.interview_status} />,
          }
        : {
            header: t("admin.applications.status"),
            render: (row) => <ApplicationStatusBadge value={row.application_status} />,
          },
      {
        header: candidates ? t("admin.applications.candidateSince") : t("admin.applications.submitted"),
        sortKey: candidates ? "candidate_at" : "submitted_at",
        hideOnMobile: true,
        render: (row) => (
          <span className="table-muted admin-nowrap">
            {formatDate((candidates && row.candidate_at) || row.submitted_at)}
          </span>
        ),
      },
    ],
    [t, candidates, detailBase, statusLabel],
  );

  const options = (group: string, list: string[]) =>
    list.map((value) => ({ value, label: statusLabel(group, value) }));

  return (
    <div className="page">
      <PageMeta title={t(candidates ? "admin.nav.candidates" : "admin.nav.applications")} noindex />
      <PageHeader
        title={t(candidates ? "admin.candidates.title" : "admin.applications.title")}
        description={t(candidates ? "admin.candidates.description" : "admin.applications.description")}
      />

      {!summary ? (
        <SkeletonCards count={4} />
      ) : candidates ? (
        <div className="stat-grid">
          <StatCard label={t("admin.candidates.total")} value={summary.total} />
          {HIRING_STATUSES.slice(0, 3).map((status) => (
            <StatCard
              key={status}
              label={statusLabel("hiring", status)}
              value={summary.hiring_status[status] ?? 0}
            />
          ))}
        </div>
      ) : (
        <div className="stat-grid">
          <StatCard label={t("admin.applications.total")} value={summary.total} />
          <StatCard
            label={t("admin.applications.analyzed")}
            value={summary.analysis_status.completed ?? 0}
            tone="success"
          />
          <StatCard
            label={t("admin.applications.notAnalyzed")}
            value={(summary.analysis_status.new ?? 0) + (summary.analysis_status.pending ?? 0)}
          />
          <StatCard
            label={t("admin.applications.failed")}
            value={summary.analysis_status.failed ?? 0}
            tone={(summary.analysis_status.failed ?? 0) > 0 ? "danger" : "default"}
          />
        </div>
      )}

      <Card flush>
        <FilterBar
          search={{
            value: search,
            onChange: setSearch,
            placeholder: t("admin.applications.searchPlaceholder"),
          }}
          active={active}
          onClear={clear}
        >
          <OwnerSelect value={values.owner_id} onChange={(owner_id) => setFilters({ owner_id })} />
          <CompanySelect value={values.company} onChange={(company) => setFilters({ company })} />
          {candidates ? (
            <>
              <ToolbarSelect
                label={t("admin.applications.hiringStatus")}
                value={values.hiring_status}
                onChange={(hiring_status) => setFilters({ hiring_status })}
                allLabel={t("labels.all")}
                options={options("hiring", HIRING_STATUSES)}
              />
              <ToolbarSelect
                label={t("admin.applications.interviewStatus")}
                value={values.interview_status}
                onChange={(interview_status) => setFilters({ interview_status })}
                allLabel={t("labels.all")}
                options={options("interview", INTERVIEW_STATUSES)}
              />
            </>
          ) : (
            <ToolbarSelect
              label={t("admin.applications.status")}
              value={values.application_status}
              onChange={(application_status) => setFilters({ application_status })}
              allLabel={t("labels.all")}
              options={options("application", APPLICATION_STATUSES)}
            />
          )}
          <ToolbarSelect
            label={t("admin.applications.aiStatus")}
            value={values.analysis}
            onChange={(analysis) => setFilters({ analysis })}
            allLabel={t("labels.all")}
            options={ANALYSIS_FILTERS.map((value) => ({
              value,
              label: t(`admin.applications.analysisFilter.${value}`),
            }))}
          />
          <ToolbarSelect
            label={t("admin.applications.aiScore")}
            value={values.score}
            onChange={(score) => setFilters({ score })}
            allLabel={t("labels.all")}
            options={Object.keys(SCORE_RANGES).map((value) => ({ value, label: `${value}%` }))}
          />
          <DateRangeFields from={values.date_from} to={values.date_to} onChange={setFilters} />
        </FilterBar>

        {values.job_id && (
          <div className="admin-filter-chip-row">
            <span className="admin-chip">
              {t("admin.applications.jobFilter", { id: values.job_id })}
              <button
                type="button"
                className="admin-chip-remove"
                onClick={() => setFilters({ job_id: "" })}
                aria-label={t("common.clearFilters")}
              >
                <X size={12} aria-hidden="true" />
              </button>
            </span>
          </div>
        )}

        <ServerTable
          columns={columns}
          data={query.data}
          loading={query.loading}
          error={query.error}
          onRetry={query.reload}
          rowKey={(row) => row.id}
          caption={t(candidates ? "admin.candidates.title" : "admin.applications.title")}
          onPageChange={setPage}
          sort={{ key: values.sort, order: values.order as "asc" | "desc" }}
          onSortChange={(key) => setFilters(nextSort(values, key))}
          filtered={active}
          onClearFilters={clear}
          emptyTitle={t(candidates ? "admin.candidates.emptyTitle" : "admin.applications.emptyTitle")}
          emptyMessage={t(candidates ? "admin.candidates.emptyMessage" : "admin.applications.emptyMessage")}
        />
      </Card>
    </div>
  );
}
