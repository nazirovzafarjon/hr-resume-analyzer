import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { Pencil, ShieldOff, ShieldPlus, Trash2, UserCheck, UserX } from "lucide-react";
import PageHeader from "../../components/ui/PageHeader";
import PageMeta from "../../components/seo/PageMeta";
import Button from "../../components/ui/Button";
import Card from "../../components/ui/Card";
import EmptyState from "../../components/ui/EmptyState";
import StatCard from "../../components/ui/StatCard";
import { SkeletonCards, SkeletonText } from "../../components/ui/Skeleton";
import { AnalysisStatusBadge, ApplicationStatusBadge } from "../../components/ui/ApplicationStatusBadge";
import AuditActivityList from "../../components/admin/AuditActivityList";
import EditUserDialog from "../../components/admin/EditUserDialog";
import UserActionDialog, { type UserAction } from "../../components/admin/UserActionDialog";
import { AccountStatusBadge, RoleBadge } from "../../components/admin/badges";
import { useLanguage } from "../../contexts/LanguageContext";
import { useApiQuery } from "../../hooks/useApiQuery";
import { useCurrentUser } from "../../hooks/useCurrentUser";
import { fetchAdminUser } from "../../services/adminService";
import { ApiError, getErrorMessage } from "../../utils/apiError";
import { formatDate, formatDateTime } from "../../utils/date";
import { parseId } from "./adminFormat";

export default function AdminUserDetailPage() {
  const { t } = useLanguage();
  const navigate = useNavigate();
  const userId = parseId(useParams().id);
  const { user: me } = useCurrentUser();
  const [pending, setPending] = useState<UserAction | null>(null);
  const [editing, setEditing] = useState(false);
  const { data: user, loading, error, reload } = useApiQuery(
    () => (userId ? fetchAdminUser(userId) : Promise.reject(new ApiError(404, "User not found"))),
    String(userId),
  );

  const crumbs = [{ label: t("admin.nav.users"), to: "/admin/users" }, { label: user?.full_name ?? "…" }];

  if (error && !user) {
    const notFound = error instanceof ApiError && error.status === 404;
    return (
      <div className="page">
        <PageHeader title={t("admin.users.detailTitle")} breadcrumbs={crumbs} />
        <EmptyState
          tone="error"
          title={notFound ? t("admin.users.notFoundTitle") : t("errors.loadTitle")}
          message={notFound ? t("admin.users.notFoundMessage") : getErrorMessage(error, t("errors.loadMessage"))}
          action={
            notFound ? (
              <Button variant="secondary" to="/admin/users">
                {t("admin.users.backToList")}
              </Button>
            ) : (
              <Button onClick={reload}>{t("common.retry")}</Button>
            )
          }
        />
      </div>
    );
  }

  if (loading && !user) {
    return (
      <div className="page">
        <PageHeader title={t("admin.users.detailTitle")} breadcrumbs={crumbs} />
        <SkeletonCards count={4} />
        <Card>
          <SkeletonText lines={6} />
        </Card>
      </div>
    );
  }

  if (!user) return null;
  const isSelf = user.id === me?.id;

  return (
    <div className="page">
      <PageMeta title={user.full_name} noindex />
      <PageHeader
        title={user.full_name}
        description={user.email}
        breadcrumbs={crumbs}
        action={
          <div className="admin-actions">
            <Button variant="secondary" icon={<Pencil size={15} />} onClick={() => setEditing(true)}>
              {t("admin.users.edit.action")}
            </Button>
            {/* Self-protection mirrors the backend: no self-demotion,
                deactivation or deletion is even offered. */}
            {!isSelf && (
              <>
                <Button
                  variant="secondary"
                  icon={user.is_active ? <UserX size={15} /> : <UserCheck size={15} />}
                  onClick={() => setPending(user.is_active ? "deactivate" : "activate")}
                >
                  {user.is_active ? t("admin.users.deactivate") : t("admin.users.activate")}
                </Button>
                <Button
                  variant="secondary"
                  icon={user.is_superuser ? <ShieldOff size={15} /> : <ShieldPlus size={15} />}
                  onClick={() => setPending(user.is_superuser ? "demote" : "promote")}
                >
                  {user.is_superuser ? t("admin.users.demote") : t("admin.users.promote")}
                </Button>
                <Button variant="danger-subtle" icon={<Trash2 size={15} />} onClick={() => setPending("delete")}>
                  {t("admin.users.delete")}
                </Button>
              </>
            )}
          </div>
        }
      />

      {isSelf && <p className="admin-note">{t("admin.users.selfNote")}</p>}

      <div className="stat-grid">
        <StatCard label={t("admin.users.jobs")} value={user.stats.jobs} />
        <StatCard label={t("admin.users.applications")} value={user.stats.applications} />
        <StatCard label={t("admin.dashboard.kpi.candidates")} value={user.stats.candidates} />
        <StatCard label={t("admin.dashboard.kpi.interviews")} value={user.stats.interviews} />
        <StatCard label={t("admin.users.aiAnalyses")} value={user.stats.ai_analyses} tone="info" />
        <StatCard
          label={t("admin.users.aiFailures")}
          value={user.stats.ai_runs_failed}
          tone={user.stats.ai_runs_failed > 0 ? "warning" : "default"}
        />
      </div>

      <div className="candidate-grid">
        <Card title={t("admin.users.profile")}>
          <dl className="detail-list">
            <dt>{t("admin.users.role")}</dt>
            <dd>
              <RoleBadge admin={user.is_superuser} />
            </dd>
            <dt>{t("admin.users.status")}</dt>
            <dd>
              <AccountStatusBadge active={user.is_active} />
            </dd>
            <dt>{t("admin.users.signIn")}</dt>
            <dd>
              {[user.has_password && t("admin.users.signInPassword"), user.google_linked && "Google"]
                .filter(Boolean)
                .join(" · ") || "—"}
            </dd>
            <dt>{t("admin.users.aiProvider")}</dt>
            <dd>
              {user.ai_provider_source === "custom"
                ? t("admin.users.aiProviderCustom")
                : t("admin.users.aiProviderDefault")}
            </dd>
            <dt>{t("admin.users.joined")}</dt>
            <dd>{formatDate(user.created_at)}</dd>
            <dt>{t("admin.users.lastActivity")}</dt>
            <dd>{user.last_login_at ? formatDateTime(user.last_login_at) : t("admin.users.never")}</dd>
          </dl>
        </Card>

        <Card
          title={t("admin.users.recentActivity")}
          action={<Link to={`/admin/audit-logs?actor_id=${user.id}`}>{t("admin.common.viewAll")}</Link>}
        >
          <AuditActivityList
            entries={user.recent_activity}
            emptyTitle={t("admin.dashboard.noActivityTitle")}
            emptyMessage={t("admin.users.noActivityMessage")}
          />
        </Card>
      </div>

      <div className="dashboard-grid dashboard-grid--even">
        <Card
          title={t("admin.users.recentJobs")}
          action={<Link to={`/admin/jobs?owner_id=${user.id}`}>{t("admin.common.viewAll")}</Link>}
        >
          {user.recent_jobs.length === 0 ? (
            <EmptyState title={t("admin.jobs.emptyTitle")} message={t("admin.users.noJobs")} />
          ) : (
            <ul className="admin-list">
              {user.recent_jobs.map((job) => (
                <li key={job.id}>
                  <Link to={`/admin/jobs?job=${job.id}`} className="table-primary">
                    {job.position}
                  </Link>
                  <span className="table-secondary">
                    {job.company_name} · {t("admin.jobs.applicationsCount", { count: job.applications_count })} ·{" "}
                    {formatDate(job.created_at)}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </Card>

        <Card
          title={t("admin.users.recentApplications")}
          action={<Link to={`/admin/applications?owner_id=${user.id}`}>{t("admin.common.viewAll")}</Link>}
        >
          {user.recent_applications.length === 0 ? (
            <EmptyState title={t("admin.applications.emptyTitle")} message={t("admin.users.noApplications")} />
          ) : (
            <ul className="admin-list">
              {user.recent_applications.map((application) => (
                <li key={application.id}>
                  <Link to={`/admin/applications/${application.id}`} className="table-primary">
                    {application.name}
                  </Link>
                  <span className="table-secondary">
                    {application.position} · {application.company_name} · {formatDate(application.submitted_at)}
                  </span>
                  <span className="admin-list-badges">
                    <ApplicationStatusBadge value={application.application_status} />
                    <AnalysisStatusBadge value={application.analysis_status} />
                  </span>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>

      <EditUserDialog
        user={editing ? user : null}
        isSelf={isSelf}
        onClose={() => setEditing(false)}
        onDone={() => {
          setEditing(false);
          reload();
        }}
      />

      <UserActionDialog
        pending={pending ? { action: pending, user } : null}
        onClose={() => setPending(null)}
        onDone={(action) => {
          setPending(null);
          if (action === "delete") navigate("/admin/users", { replace: true });
          else reload();
        }}
      />
    </div>
  );
}
