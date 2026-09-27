import { Link } from "react-router-dom";
import { Briefcase, FileText } from "lucide-react";
import type { RecentJob, RecentLead } from "../../services/dashboardService";
import { formatDateTime } from "../../utils/date";
import EmptyState from "../ui/EmptyState";
import { Skeleton } from "../ui/Skeleton";

type ActivityItem = {
  id: string;
  type: "job" | "application";
  title: string;
  meta: string;
  timestamp: string;
  to: string;
};

/** Chronologically merges two real feeds (recent jobs, recent applications) — no fabricated events. */
function buildActivity(jobs: RecentJob[], leads: RecentLead[]): ActivityItem[] {
  const jobItems: ActivityItem[] = jobs.map((job) => ({
    id: `job-${job.id}`,
    type: "job",
    title: job.position,
    meta: job.company_name,
    timestamp: job.created_at,
    to: `/jobs/${job.id}`,
  }));
  const leadItems: ActivityItem[] = leads.map((lead) => ({
    id: `lead-${lead.id}`,
    type: "application",
    title: lead.name,
    meta: `${lead.position} · ${lead.company_name}`,
    timestamp: lead.created_at,
    to: `/candidates/${lead.id}`,
  }));
  return [...jobItems, ...leadItems].sort(
    (a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime(),
  );
}

type RecentActivityListProps = {
  jobs: RecentJob[];
  leads: RecentLead[];
  loading?: boolean;
  jobLabel: string;
  applicationLabel: string;
  emptyTitle: string;
  emptyMessage: string;
  limit?: number;
};

export default function RecentActivityList({
  jobs,
  leads,
  loading = false,
  jobLabel,
  applicationLabel,
  emptyTitle,
  emptyMessage,
  limit = 8,
}: RecentActivityListProps) {
  if (loading) {
    return (
      <ul className="activity-list" aria-hidden="true">
        {Array.from({ length: 4 }).map((_, index) => (
          <li key={index} className="activity-item">
            <Skeleton variant="avatar" width={28} height={28} />
            <div style={{ flex: 1, minWidth: 0 }}>
              <Skeleton width="60%" height={12} />
              <Skeleton width="40%" height={10} style={{ marginTop: "var(--space-xs)" }} />
            </div>
          </li>
        ))}
      </ul>
    );
  }

  const items = buildActivity(jobs, leads).slice(0, limit);
  if (items.length === 0) {
    return <EmptyState title={emptyTitle} message={emptyMessage} />;
  }

  return (
    <ul className="activity-list">
      {items.map((item) => (
        <li key={item.id} className="activity-item">
          <span className={`activity-icon activity-icon--${item.type}`} aria-hidden="true">
            {item.type === "job" ? <Briefcase size={14} /> : <FileText size={14} />}
          </span>
          <Link to={item.to} className="activity-content">
            <span className="activity-title">
              {item.type === "job" ? jobLabel : applicationLabel}: {item.title}
            </span>
            <span className="activity-meta">{item.meta}</span>
          </Link>
          <span className="activity-time">{formatDateTime(item.timestamp)}</span>
        </li>
      ))}
    </ul>
  );
}
