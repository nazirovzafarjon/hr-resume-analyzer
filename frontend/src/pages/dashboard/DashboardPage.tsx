import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Plus, Briefcase, Users, FileText, Building2, ArrowUpRight } from "lucide-react";
import { fetchDashboardOverview, fetchRecentJobs, fetchRecentLeads } from "../../services/dashboardService";
import { formatDate } from "../../utils/date";
import { ApiError } from "../../utils/apiError";
import PageHeader from "../../components/ui/PageHeader";
import Card from "../../components/ui/Card";
import Button from "../../components/ui/Button";
import StatusBadge from "../../components/ui/StatusBadge";
import EmptyState from "../../components/ui/EmptyState";
import { SkeletonCards } from "../../components/ui/Skeleton";
import { useLanguage } from "../../contexts/LanguageContext";
import type { AnalyticsGroupBy } from "../../types/worker";

type DashboardData = {
  total_jobs: number;
  total_candidates: number;
  total_leads: number;
  group_by: string;
  breakdown: Array<{
    category: string;
    jobs: number;
    candidates: number;
  }>;
};

type RecentJob = {
  id: number;
  company_name: string;
  position: string;
  leads_count: number;
  created_at: string;
};

type RecentLead = {
  id: number;
  name: string;
  email: string;
  company_name: string;
  position: string;
  hiring_status: "strong_hire" | "hire" | "weak_hire" | "do_not_hire";
  created_at: string;
};

/** /dashboard — hiring analytics, pipeline KPIs and recent activity. */
export default function DashboardPage() {
  const { t } = useLanguage();
  const [groupBy, setGroupBy] = useState<AnalyticsGroupBy>("company");
  const [data, setData] = useState<DashboardData | null>(null);
  const [recentJobs, setRecentJobs] = useState<RecentJob[]>([]);
  const [recentLeads, setRecentLeads] = useState<RecentLead[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const groupOptions: { value: AnalyticsGroupBy; label: string }[] = [
    { value: "company", label: t("dashboard.company") || "Company" },
    { value: "position", label: t("dashboard.position") || "Position" },
    { value: "experience", label: t("dashboard.experience") || "Experience" },
  ];

  useEffect(() => {
    let mounted = true;

    async function loadDashboard() {
      setLoading(true);
      setError(null);

      try {
        const [overview, jobs, leads] = await Promise.all([
          fetchDashboardOverview(groupBy),
          fetchRecentJobs(4),
          fetchRecentLeads(5),
        ]);

        if (mounted) {
          setData(overview);
          setRecentJobs(jobs);
          setRecentLeads(leads);
        }
      } catch (err) {
        if (mounted) {
          if (err instanceof ApiError) {
            setError(err.message);
          } else {
            setError(t("dashboard.error") || "Failed to load dashboard data. Please try again.");
          }
        }
      } finally {
        if (mounted) {
          setLoading(false);
        }
      }
    }

    loadDashboard();
    return () => {
      mounted = false;
    };
  }, [groupBy, t]);

  const handleGroupChange = async (newGroupBy: AnalyticsGroupBy) => {
    setGroupBy(newGroupBy);
    setLoading(true);
    setError(null);

    try {
      const overview = await fetchDashboardOverview(newGroupBy);
      if (data) {
        setData({ ...overview });
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t("dashboard.error") || "Failed to load analytics.");
    } finally {
      setLoading(false);
    }
  };

  const breakdown = data?.breakdown ?? [];
  const maxCandidates = Math.max(1, ...breakdown.map((entry) => entry.candidates));

  if (loading && !data) {
    return (
      <div className="page">
        <PageHeader
          title={t("dashboard.title")}
          description={t("dashboard.description")}
          action={
            <Button to="/jobs/create" icon={<Plus size={16} />}>
              {t("jobs.createJob") || "Create Job"}
            </Button>
          }
        />
        <SkeletonCards count={4} />
      </div>
    );
  }

  if (error && !data) {
    return (
      <div className="page">
        <PageHeader
          title={t("dashboard.title")}
          description={t("dashboard.description")}
          action={
            <Button to="/jobs/create" icon={<Plus size={16} />}>
              {t("jobs.createJob") || "Create Job"}
            </Button>
          }
        />
        <Card>
          <EmptyState
            tone="error"
            title={t("dashboard.error") || "Unable to load dashboard"}
            message={error}
            action={
              <Button onClick={() => window.location.reload()}>{t("common.retry") || "Retry"}</Button>
            }
          />
        </Card>
      </div>
    );
  }

  const selectedGroupLabel = groupOptions.find((o) => o.value === groupBy)?.label ?? groupBy;

  return (
    <div className="page">
      <PageHeader
        title={t("dashboard.title")}
        description={t("dashboard.description")}
        action={
          <Button to="/jobs/create" icon={<Plus size={16} />}>
            {t("jobs.createJob") || "Create Job"}
          </Button>
        }
      />

      <div className="kpi-grid">
        <div className="kpi-card">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
            <p className="kpi-label">{t("stats.jobs") || "Open Jobs"}</p>
            <span style={{ color: "var(--color-primary)", opacity: 0.8 }}><Briefcase size={16} /></span>
          </div>
          <p className="kpi-value">{data?.total_jobs ?? 0}</p>
          <p className="kpi-hint">{t("stats.jobsHint") || "active vacancies"}</p>
          <span className="kpi-trend">{data?.total_jobs ?? 0} {t("nav.jobs") || "jobs"}</span>
        </div>

        <div className="kpi-card">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
            <p className="kpi-label">{t("stats.candidates") || "Candidates"}</p>
            <span style={{ color: "var(--color-info)", opacity: 0.8 }}><Users size={16} /></span>
          </div>
          <p className="kpi-value">{data?.total_candidates ?? 0}</p>
          <p className="kpi-hint">{t("stats.candidatesHint") || "in pipeline"}</p>
          <span className="kpi-trend">{t("stats.applicationsHint") || "total received"}</span>
        </div>

        <div className="kpi-card">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
            <p className="kpi-label">{t("stats.leads") || "Total Leads"}</p>
            <span style={{ color: "var(--color-success)", opacity: 0.8 }}><FileText size={16} /></span>
          </div>
          <p className="kpi-value">{data?.total_leads ?? 0}</p>
          <p className="kpi-hint">{t("stats.leadsHint") || "leads count"}</p>
          <span className="kpi-trend">all time</span>
        </div>

        <div className="kpi-card">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
            <p className="kpi-label">{t("dashboard.groupBy") || "Dimension"}</p>
            <span style={{ color: "var(--color-warning)", opacity: 0.8 }}><Building2 size={16} /></span>
          </div>
          <p className="kpi-value">{breakdown.length}</p>
          <p className="kpi-hint">{selectedGroupLabel}</p>
          <span className="kpi-trend">{groupBy}</span>
        </div>
      </div>

      <div className="dashboard-grid">
        <Card
          title={`${t("nav.candidates") || "Candidates"} — ${selectedGroupLabel}`}
          subtitle={`${t("dashboard.groupBy") || "Grouped by"}: ${selectedGroupLabel}`}
          action={
            <div className="segmented" role="group" aria-label="Analytics dimension">
              {groupOptions.map((option) => (
                <button
                  key={option.value}
                  type="button"
                  className={`segmented-button${groupBy === option.value ? " is-active" : ""}`}
                  onClick={() => handleGroupChange(option.value)}
                  disabled={loading}
                >
                  {option.label}
                </button>
              ))}
            </div>
          }
        >
          {loading ? (
            <p className="muted-note">{t("common.loading") || "Loading analytics..."}</p>
          ) : breakdown.length === 0 ? (
            <p className="muted-note">{t("common.noData") || "No analytics to display yet."}</p>
          ) : (
            <ul className="bar-list">
              {breakdown.map((entry) => (
                <li key={entry.category} className="bar-item">
                  <span className="bar-label" title={entry.category}>
                    {entry.category}
                  </span>
                  <span className="bar-track">
                    <span
                      className="bar-fill"
                      style={{ width: `${(entry.candidates / maxCandidates) * 100}%` }}
                    />
                  </span>
                  <span className="bar-value">{entry.candidates}</span>
                </li>
              ))}
            </ul>
          )}
        </Card>

        <Card
          title={t("dashboard.recentJobs") || "Recent Jobs"}
          action={
            <Link className="link" to="/jobs" style={{ display: "inline-flex", alignItems: "center", gap: "4px" }}>
              {t("dashboard.viewAll") || "View all"} <ArrowUpRight size={14} />
            </Link>
          }
        >
          {recentJobs.length === 0 ? (
            <p className="muted-note">{t("dashboard.noJobs") || "No jobs yet."}</p>
          ) : (
            <ul className="recent-jobs">
              {recentJobs.map((job) => (
                <li key={job.id}>
                  <Link className="recent-jobs-link" to={`/jobs/${job.id}`}>
                    <span className="recent-jobs-title">{job.position}</span>
                    <span className="recent-jobs-meta">
                      {job.company_name} · {job.leads_count} {t("jobs.leads") || "leads"}
                    </span>
                  </Link>
                  <span className="recent-jobs-date">{formatDate(job.created_at)}</span>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>

      <Card
        title={t("dashboard.recentCandidates") || "Recent Candidates"}
        action={
          <Link className="link" to="/candidates" style={{ display: "inline-flex", alignItems: "center", gap: "4px" }}>
            {t("dashboard.viewAll") || "View all"} <ArrowUpRight size={14} />
          </Link>
        }
      >
        {recentLeads.length === 0 ? (
          <p className="muted-note">{t("dashboard.noCandidates") || "No candidates yet."}</p>
        ) : (
          <ul className="recent-candidates">
            {recentLeads.map((candidate) => (
              <li key={candidate.id}>
                <Link className="recent-candidates-link" to={`/candidates/${candidate.id}`}>
                  <span className="recent-candidates-name">{candidate.name}</span>
                  <span className="recent-candidates-meta">
                    {candidate.position} · {candidate.company_name}
                  </span>
                </Link>
                <div className="recent-candidates-status">
                  <StatusBadge kind="hiring" value={candidate.hiring_status} />
                </div>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}
