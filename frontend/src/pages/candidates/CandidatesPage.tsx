import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Search } from "lucide-react";
import { fetchCandidates } from "../../services/workersService";
import PageHeader from "../../components/ui/PageHeader";
import PageMeta from "../../components/seo/PageMeta";
import Button from "../../components/ui/Button";
import Card from "../../components/ui/Card";
import EmptyState from "../../components/ui/EmptyState";
import StatusBadge from "../../components/ui/StatusBadge";
import StatCard from "../../components/ui/StatCard";
import Table, { type TableColumn } from "../../components/ui/Table";
import { SkeletonCards } from "../../components/ui/Skeleton";
import { useLanguage } from "../../contexts/LanguageContext";
import { getErrorMessage } from "../../utils/apiError";
import { formatDate } from "../../utils/date";
import type { Candidate, HiringStatus, InterviewStatus } from "../../types/worker";

const HIRING_STATUSES: HiringStatus[] = ["strong_hire", "hire", "weak_hire", "do_not_hire"];
const INTERVIEW_STATUSES: InterviewStatus[] = ["in_process", "completed", "not_completed"];
const HIRING_TONES = { strong_hire: "success", hire: "info", weak_hire: "warning", do_not_hire: "danger" } as const;

export default function CandidatesPage() {
  const { t } = useLanguage();
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reload, setReload] = useState(0);
  const [search, setSearch] = useState("");
  const [hiringFilter, setHiringFilter] = useState<HiringStatus | "all">("all");
  const [interviewFilter, setInterviewFilter] = useState<InterviewStatus | "all">("all");

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    fetchCandidates()
      .then((data) => { if (!cancelled) setCandidates(data); })
      .catch((err: unknown) => {
        if (!cancelled) setError(getErrorMessage(err, t("errors.loadMessage")));
      })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [t, reload]);

  const stats = useMemo(() => {
    type StatusCount = Record<HiringStatus, number>;
    const counts = HIRING_STATUSES.reduce((acc, status) => ({ ...acc, [status]: 0 }), {} as StatusCount);
    candidates.forEach((candidate) => {
      counts[candidate.hiring_status] = (counts[candidate.hiring_status] ?? 0) + 1;
    });
    return { total: candidates.length, counts };
  }, [candidates]);

  const filteredCandidates = useMemo(() => {
    const query = search.trim().toLowerCase();
    return candidates.filter((candidate) => {
      const matchesSearch = !query ||
        candidate.name.toLowerCase().includes(query) ||
        candidate.email.toLowerCase().includes(query) ||
        candidate.position.toLowerCase().includes(query) ||
        candidate.company_name.toLowerCase().includes(query);
      const matchesHiring = hiringFilter === "all" || candidate.hiring_status === hiringFilter;
      const matchesInterview = interviewFilter === "all" || candidate.interview_status === interviewFilter;
      return matchesSearch && matchesHiring && matchesInterview;
    });
  }, [candidates, search, hiringFilter, interviewFilter]);

  const columns = useMemo<TableColumn<Candidate>[]>(() => [
    {
      header: t("candidates.name"),
      sort: (a, b) => a.name.localeCompare(b.name),
      render: (candidate) => (
        <div>
          <Link className="table-primary" to={`/candidates/${candidate.id}`}>
            {candidate.name}
          </Link>
          <div className="table-secondary">{candidate.email}</div>
        </div>
      ),
    },
    {
      header: t("candidates.position"),
      render: (candidate) => (
        <div>
          <div className="table-primary">{candidate.position || "—"}</div>
          <div className="table-secondary">{candidate.company_name || "—"}</div>
        </div>
      ),
    },
    {
      header: t("candidates.aiScore"),
      sort: (a, b) =>
        (a.analysis_status === "completed" ? a.ai_score : -1) -
        (b.analysis_status === "completed" ? b.ai_score : -1),
      render: (candidate) => (
        <span className="table-number">
          {candidate.analysis_status === "completed" && Number.isFinite(candidate.ai_score)
            ? `${Math.round(candidate.ai_score)}%` : "—"}
        </span>
      ),
    },
    {
      header: t("candidates.hiringStatus"),
      render: (candidate) => <StatusBadge kind="hiring" value={candidate.hiring_status} />,
    },
    {
      header: t("candidates.interviewStatus"),
      render: (candidate) => <StatusBadge kind="interview" value={candidate.interview_status} />,
    },
    {
      header: t("candidates.created"),
      sort: (a, b) =>
        Date.parse(a.submitted_at || a.created_at) - Date.parse(b.submitted_at || b.created_at),
      render: (candidate) => (
        <span className="table-muted">
          {formatDate(candidate.submitted_at || candidate.created_at)}
        </span>
      ),
    },
    {
      header: t("labels.actions"),
      headerClassName: "table-actions-cell",
      className: "table-actions-cell",
      render: (candidate) => (
        <Link className="row-action" to={`/candidates/${candidate.id}`}>
          {t("candidates.view")}
        </Link>
      ),
    },
  ], [t]);

  return (
    <div className="page">
      <PageMeta title={t("nav.candidates")} noindex />
      <PageHeader title={t("candidates.title")} description={t("candidates.description")} />

      {loading ? <SkeletonCards count={4} /> : (
        <div className="stat-grid">
          {HIRING_STATUSES.map((status) => (
            <StatCard
              key={status}
              label={t(`statusMeta.hiring.${status}`)}
              value={stats.counts[status]}
              tone={HIRING_TONES[status]}
                            hint=""
            />
          ))}
        </div>
      )}

      <Card flush>
        <div className="candidate-toolbar">
          <label className="toolbar-label toolbar-label--grow">
            {t("common.search")}
            <span className="search-field">
              <span className="search-field-icon" aria-hidden="true">
                <Search size={15} />
              </span>
              <input
                className="field-input"
                type="search"
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder={t("searchPlaceholder")}
                aria-label={t("searchPlaceholder")}
              />
            </span>
          </label>

          <label className="toolbar-label">
            {t("hiringFilter")}
            <select
              className="field-select"
              value={hiringFilter}
              onChange={(event) => setHiringFilter(event.target.value as typeof hiringFilter)}
            >
                            <option value="all">{t("labels.all")}</option>
              {HIRING_STATUSES.map((status) => (
                <option key={status} value={status}>
                  {t(`statusMeta.hiring.${status}`)}
                </option>
              ))}
            </select>
          </label>

          <label className="toolbar-label">
            {t("interviewFilter")}
            <select
              className="field-select"
              value={interviewFilter}
              onChange={(event) => setInterviewFilter(event.target.value as typeof interviewFilter)}
            >
              <option value="all">{t("labels.all")}</option>
              {INTERVIEW_STATUSES.map((status) => (
                <option key={status} value={status}>
                  {t(`statusMeta.interview.${status}`)}
                </option>
              ))}
            </select>
          </label>
        </div>

        {error ? (
          <EmptyState
            tone="error"
            title={t("errors.loadTitle")}
            message={error}
            action={
              <Button variant="secondary" onClick={() => setReload((v) => v + 1)}>
                {t("common.retry")}
              </Button>
            }
          />
        ) : (
          <Table
            rows={filteredCandidates}
            columns={columns}
            rowKey={(candidate) => candidate.id}
            loading={loading}
            caption={t("candidates.title")}
            emptyState={
              <EmptyState
                title={t("candidates.noCandidates")}
                message={t("candidates.noCandidatesDescription")}
                action={<Link className="btn btn--primary" to="/applications">{t("nav.applications")}</Link>}
              />
            }
          />
        )}
      </Card>
    </div>
  );
}
