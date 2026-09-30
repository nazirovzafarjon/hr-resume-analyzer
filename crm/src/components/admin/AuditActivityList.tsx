import { Link } from "react-router-dom";
import {
  Bot,
  Briefcase,
  CalendarDays,
  FileText,
  Settings as SettingsIcon,
  UserRound,
  type LucideIcon,
} from "lucide-react";
import EmptyState from "../ui/EmptyState";
import { useLanguage } from "../../contexts/LanguageContext";
import { formatDateTime } from "../../utils/date";
import { translateOr } from "../../utils/statusLabels";
import type { AuditLogEntry } from "../../types/admin";

const RESOURCE_ICONS: Record<string, LucideIcon> = {
  user: UserRound,
  job: Briefcase,
  application: FileText,
  interview: CalendarDays,
  ai_analysis: Bot,
  settings: SettingsIcon,
};

/** "CREATE_JOB" -> "Create job" when no translation exists. */
function humanize(action: string): string {
  const words = action.toLowerCase().split("_");
  return [words[0]!.charAt(0).toUpperCase() + words[0]!.slice(1), ...words.slice(1)].join(" ");
}

export function useAuditActionLabel() {
  const { t } = useLanguage();
  return (action: string) => translateOr(t, `admin.audit.actions.${action}`, humanize(action));
}

/** Admin page that shows a resource, when one exists and still makes sense. */
export function auditResourceLink(entry: AuditLogEntry): string | null {
  if (!entry.resource_id || entry.action.startsWith("DELETE_")) return null;
  switch (entry.resource_type) {
    case "user":
      return `/admin/users/${entry.resource_id}`;
    case "application":
      return `/admin/applications/${entry.resource_id}`;
    case "job":
      return `/admin/jobs?job=${entry.resource_id}`;
    default:
      return null;
  }
}

/** Compact activity feed built from real audit rows (dashboard, user detail). */
export default function AuditActivityList({
  entries,
  emptyTitle,
  emptyMessage,
}: {
  entries: AuditLogEntry[];
  emptyTitle: string;
  emptyMessage: string;
}) {
  const { t } = useLanguage();
  const actionLabel = useAuditActionLabel();

  if (entries.length === 0) return <EmptyState title={emptyTitle} message={emptyMessage} />;

  return (
    <ul className="activity-list">
      {entries.map((entry) => {
        const Icon = RESOURCE_ICONS[entry.resource_type] ?? FileText;
        const link = auditResourceLink(entry);
        const title = actionLabel(entry.action);
        const meta = [
          entry.actor_email ?? t("admin.audit.system"),
          entry.resource_id ? `${entry.resource_type} #${entry.resource_id}` : entry.resource_type,
        ].join(" · ");
        const content = (
          <>
            <span className="activity-title">{title}</span>
            <span className="activity-meta">{meta}</span>
          </>
        );
        return (
          <li key={entry.id} className="activity-item">
            <span className="activity-icon activity-icon--job" aria-hidden="true">
              <Icon size={14} />
            </span>
            {link ? (
              <Link to={link} className="activity-content">
                {content}
              </Link>
            ) : (
              <span className="activity-content">{content}</span>
            )}
            <span className="activity-time">{formatDateTime(entry.created_at)}</span>
          </li>
        );
      })}
    </ul>
  );
}
