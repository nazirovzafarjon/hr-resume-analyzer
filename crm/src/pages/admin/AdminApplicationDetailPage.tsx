import { Link, useLocation, useParams } from "react-router-dom";
import { Bot, Pencil } from "lucide-react";
import PageHeader from "../../components/ui/PageHeader";
import PageMeta from "../../components/seo/PageMeta";
import Button from "../../components/ui/Button";
import Card from "../../components/ui/Card";
import EmptyState from "../../components/ui/EmptyState";
import InterviewStatusBadge from "../../components/ui/InterviewStatusBadge";
import StatusBadge from "../../components/ui/StatusBadge";
import { SkeletonText } from "../../components/ui/Skeleton";
import { AnalysisStatusBadge, ApplicationStatusBadge } from "../../components/ui/ApplicationStatusBadge";
import ApplicationAnswers from "../../components/applications/ApplicationAnswers";
import { formatScore } from "../../components/admin/badges";
import { useLanguage } from "../../contexts/LanguageContext";
import { useApiQuery } from "../../hooks/useApiQuery";
import { fetchAdminApplication } from "../../services/adminService";
import { ApiError, getErrorMessage } from "../../utils/apiError";
import { formatDate, formatDateTime } from "../../utils/date";
import { translateOr } from "../../utils/statusLabels";
import { parseId } from "./adminFormat";

function BulletList({ title, items }: { title: string; items: string[] }) {
  if (items.length === 0) return null;
  return (
    <div className="admin-analysis-block">
      <h3 className="mini-heading">{title}</h3>
      <ul className="bullet-list">
        {items.map((item, index) => (
          <li key={index}>{item}</li>
        ))}
      </ul>
    </div>
  );
}

/**
 * Application / candidate overview for administrators.
 *
 * The AI result is shown as system-generated analysis, clearly separated from
 * the human decisions (application, hiring and interview status). Admins have
 * every HR permission: "Manage" opens the same record in the hiring workspace,
 * where the admin changes statuses, runs the AI analysis and schedules
 * interviews with the regular HR screens (the API scopes an admin session to
 * every HR user's data).
 */
export default function AdminApplicationDetailPage() {
  const { t } = useLanguage();
  const { pathname } = useLocation();
  const workerId = parseId(useParams().id);
  const fromCandidates = pathname.startsWith("/admin/candidates");
  const listPath = fromCandidates ? "/admin/candidates" : "/admin/applications";
  const listLabel = t(fromCandidates ? "admin.nav.candidates" : "admin.nav.applications");

  const { data: item, loading, error, reload } = useApiQuery(
    () =>
      workerId ? fetchAdminApplication(workerId) : Promise.reject(new ApiError(404, "Application not found")),
    String(workerId),
  );
  const crumbs = [{ label: listLabel, to: listPath }, { label: item?.name ?? "…" }];

  if (error && !item) {
    const notFound = error instanceof ApiError && error.status === 404;
    return (
      <div className="page">
        <PageHeader title={t("admin.applications.detailTitle")} breadcrumbs={crumbs} />
        <EmptyState
          tone="error"
          title={notFound ? t("admin.applications.notFoundTitle") : t("errors.loadTitle")}
          message={notFound ? t("admin.applications.notFoundMessage") : getErrorMessage(error, t("errors.loadMessage"))}
          action={
            notFound ? (
              <Button variant="secondary" to={listPath}>
                {listLabel}
              </Button>
            ) : (
              <Button onClick={reload}>{t("common.retry")}</Button>
            )
          }
        />
      </div>
    );
  }

  if (loading || !item) {
    return (
      <div className="page">
        <PageHeader title={t("admin.applications.detailTitle")} breadcrumbs={crumbs} />
        <Card>
          <SkeletonText lines={8} />
        </Card>
      </div>
    );
  }

  const analysis = item.analysis;

  return (
    <div className="page">
      <PageMeta title={item.name} noindex />
      <PageHeader
        title={item.name}
        description={`${item.position} · ${item.company_name}`}
        breadcrumbs={crumbs}
        action={
          <Button
            icon={<Pencil size={15} />}
            to={item.is_candidate ? `/candidates/${item.id}` : `/applications/${item.id}`}
          >
            {t("admin.common.manage")}
          </Button>
        }
      />

      <p className="admin-note">{t("admin.applications.manageNote")}</p>

      <div className="candidate-grid">
        <Card title={t("admin.applications.applicationInfo")}>
          <dl className="detail-list">
            <dt>{t("admin.applications.email")}</dt>
            <dd>{item.email}</dd>
            <dt>{t("admin.applications.job")}</dt>
            <dd>
              <Link to={`/admin/jobs?job=${item.job_id}`}>{item.position}</Link> · {item.company_name}
            </dd>
            <dt>{t("admin.applications.owner")}</dt>
            <dd>
              <Link to={`/admin/users/${item.owner_id}`}>{item.owner_name}</Link> ({item.owner_email})
            </dd>
            <dt>{t("admin.applications.submitted")}</dt>
            <dd>{formatDateTime(item.submitted_at)}</dd>
            <dt>{t("admin.applications.resume")}</dt>
            <dd>{item.has_resume ? t("admin.applications.resumeOnFile") : t("admin.applications.noResume")}</dd>
          </dl>
        </Card>

        <Card title={t("admin.applications.humanDecisions")} subtitle={t("admin.applications.humanDecisionsHint")}>
          <dl className="detail-list">
            <dt>{t("admin.applications.status")}</dt>
            <dd>
              <ApplicationStatusBadge value={item.application_status} />
            </dd>
            <dt>{t("admin.applications.pipeline")}</dt>
            <dd>
              {item.is_candidate && item.candidate_at
                ? t("admin.applications.candidateSinceDate", { date: formatDate(item.candidate_at) })
                : t("admin.applications.applicationStage")}
            </dd>
            <dt>{t("admin.applications.hiringStatus")}</dt>
            <dd>
              <StatusBadge kind="hiring" value={item.hiring_status} />
            </dd>
            <dt>{t("admin.applications.interviewStatus")}</dt>
            <dd>
              <StatusBadge kind="interview" value={item.interview_status} />
            </dd>
          </dl>
        </Card>
      </div>

      <Card
        title={t("admin.applications.aiAnalysis")}
        subtitle={t("admin.applications.aiAnalysisHint")}
        icon={<Bot size={16} />}
        action={<AnalysisStatusBadge value={item.analysis_status} />}
      >
        {item.analysis_status === "failed" && item.analysis_error && (
          <p className="admin-error-text">{item.analysis_error}</p>
        )}
        {!analysis ? (
          <p className="table-muted">{t("admin.applications.noAnalysis")}</p>
        ) : (
          <div className="admin-analysis">
            <dl className="detail-list">
              <dt>{t("admin.applications.aiScore")}</dt>
              <dd>{formatScore(analysis.match_percentage)}</dd>
              <dt>{t("admin.applications.aiRecommendation")}</dt>
              <dd>
                {analysis.ai_recommendation
                  ? translateOr(t, `statusMeta.hiring.${analysis.ai_recommendation}`, analysis.ai_recommendation)
                  : "—"}
              </dd>
              {analysis.analyzed_at && (
                <>
                  <dt>{t("admin.applications.analyzedAt")}</dt>
                  <dd>
                    {formatDateTime(analysis.analyzed_at)}
                    {analysis.model ? ` · ${analysis.model}` : ""}
                  </dd>
                </>
              )}
            </dl>
            {analysis.summary && <p className="detail-description">{analysis.summary}</p>}
            <div className="dashboard-grid dashboard-grid--even">
              <BulletList title={t("admin.applications.matched")} items={analysis.matched_requirements} />
              <BulletList title={t("admin.applications.missing")} items={analysis.missing_requirements} />
              <BulletList title={t("admin.applications.strengths")} items={analysis.strengths} />
              <BulletList title={t("admin.applications.weaknesses")} items={analysis.weaknesses} />
            </div>
          </div>
        )}
      </Card>

      <div className="dashboard-grid dashboard-grid--even">
        <Card title={t("admin.applications.answers")}>
          {item.responses.length === 0 ? (
            <p className="table-muted">{t("admin.applications.noAnswers")}</p>
          ) : (
            <ApplicationAnswers answers={item.responses} />
          )}
        </Card>
        <Card title={t("admin.applications.interviews")}>
          {item.interviews.length === 0 ? (
            <p className="table-muted">{t("admin.applications.noInterviews")}</p>
          ) : (
            <ul className="admin-list">
              {item.interviews.map((interview) => (
                <li key={interview.id}>
                  <span className="table-primary">{formatDateTime(interview.scheduled_at)}</span>
                  <span className="table-secondary">{interview.interviewer}</span>
                  <span className="admin-list-badges">
                    <InterviewStatusBadge value={interview.status} />
                  </span>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>
    </div>
  );
}
