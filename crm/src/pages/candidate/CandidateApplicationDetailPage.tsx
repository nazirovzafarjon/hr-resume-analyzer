import { useState } from "react";
import { useParams } from "react-router-dom";
import { Download, Info } from "lucide-react";
import Button from "../../components/ui/Button";
import BackButton from "../../components/ui/BackButton";
import Card from "../../components/ui/Card";
import PageMeta from "../../components/seo/PageMeta";
import ApplicationTimeline from "../../components/candidate/ApplicationTimeline";
import CandidateStatusBadge from "../../components/candidate/CandidateStatusBadge";
import CompatibilityCard from "../../components/candidate/CompatibilityCard";
import InterviewItem from "../../components/candidate/InterviewItem";
import { PortalError, PortalLoading } from "../../components/candidate/PortalStates";
import { portalDate } from "../../components/candidate/portalFormat";
import { useLanguage } from "../../contexts/LanguageContext";
import { useNotify } from "../../contexts/ToastContext";
import { useApiQuery } from "../../hooks/useApiQuery";
import { downloadCandidateResume, fetchCandidateApplication } from "../../services/candidatePortalService";
import type { CandidateAnswer } from "../../types/candidatePortal";
import { ApiError, getErrorMessage } from "../../utils/apiError";

function answerText(answer: CandidateAnswer, attached: string): string {
  if (answer.type === "file") return answer.file_attached ? attached : "—";
  if (Array.isArray(answer.value)) return answer.value.join(", ") || "—";
  return answer.value ?? "—";
}

/**
 * /candidate/applications/:id — everything about one application:
 * where it stands and what happens next, the timeline, the resume/job
 * compatibility, interviews, the job and what was submitted.
 */
export default function CandidateApplicationDetailPage() {
  const { t } = useLanguage();
  const notify = useNotify();
  const id = Number(useParams().id);
  const validId = Number.isInteger(id) && id > 0;
  const { data, loading, error, reload } = useApiQuery(
    () => (validId ? fetchCandidateApplication(id) : Promise.reject(new ApiError(404, "Application not found"))),
    String(id),
  );
  const [downloading, setDownloading] = useState(false);

  async function handleDownload() {
    setDownloading(true);
    try {
      const blob = await downloadCandidateResume(id);
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = "resume";
      link.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      notify.error(t("portal.detail.downloadFailed"), getErrorMessage(err));
    } finally {
      setDownloading(false);
    }
  }

  const back = (
    <BackButton
      fallbackPath="/candidate/applications"
      label={t("portal.detail.back")}
      variant="ghost"
      size="sm"
      iconSize={14}
    />
  );

  if (error && !data) {
    return (
      <div>
        {back}
        <div className="portal-section">
          <PortalError error={error} what={t("portal.detail.what")} onRetry={reload} />
        </div>
      </div>
    );
  }
  if (loading || !data) {
    return (
      <div>
        {back}
        <div className="portal-section">
          <PortalLoading />
        </div>
      </div>
    );
  }

  const { job } = data;

  return (
    <div>
      <PageMeta title={`${job.position} · ${job.company_name}`} noindex />
      {back}
      <section className="portal-welcome" style={{ marginTop: "var(--space-md)" }}>
        <h1>{job.position}</h1>
        <p>{job.company_name}</p>
      </section>

      <div className="portal-section">
        <Card>
          <dl className="portal-facts">
            <dt>{t("portal.card.status")}</dt>
            <dd>
              <CandidateStatusBadge status={data.status} />
            </dd>
            <dt>{t("portal.card.applied")}</dt>
            <dd>{portalDate(data.submitted_at)}</dd>
          </dl>
          <p className="portal-note" style={{ marginTop: "var(--space-md)", display: "flex", gap: 8 }}>
            <Info size={16} aria-hidden="true" style={{ flexShrink: 0, marginTop: 2 }} />
            <span>
              <strong>{t("portal.detail.whatNext")}</strong> {t(`portal.next.${data.status}`)}
            </span>
          </p>
        </Card>
      </div>

      <div className="portal-section portal-two-col">
        <div className="portal-stack">
          <Card title={t("portal.detail.progress")}>
            <ApplicationTimeline steps={data.timeline} />
          </Card>

          <CompatibilityCard analysis={data.analysis} />

          <Card title={t("portal.detail.job")}>
            {job.description ? <p className="portal-prewrap">{job.description}</p> : <p className="portal-muted">—</p>}
            <dl className="portal-facts" style={{ marginTop: "var(--space-md)" }}>
              {job.required_skills && (
                <>
                  <dt>{t("portal.detail.skills")}</dt>
                  <dd>{job.required_skills}</dd>
                </>
              )}
              {job.required_experience && (
                <>
                  <dt>{t("portal.detail.experience")}</dt>
                  <dd>{job.required_experience}</dd>
                </>
              )}
            </dl>
          </Card>
        </div>

        <div className="portal-stack">
          <Card title={t("portal.detail.interviews")}>
            {data.interviews.length === 0 ? (
              <>
                <p className="portal-timeline-title" style={{ marginTop: 0 }}>
                  {t("portal.interviews.emptyTitle")}
                </p>
                <p className="portal-muted" style={{ marginBottom: 0 }}>
                  {t("portal.interviews.emptyMessage")}
                </p>
              </>
            ) : (
              data.interviews.map((interview) => (
                <InterviewItem key={interview.id} interview={interview} showJob={false} />
              ))
            )}
          </Card>

          <Card title={t("portal.detail.submitted")}>
            <dl className="portal-facts">
              {data.answers.map((answer, index) => (
                <div key={index} style={{ display: "contents" }}>
                  <dt>{answer.label}</dt>
                  <dd style={{ overflowWrap: "anywhere" }}>{answerText(answer, t("portal.detail.fileAttached"))}</dd>
                </div>
              ))}
            </dl>
            {data.answers.length === 0 && <p className="portal-muted">{t("portal.detail.noAnswers")}</p>}
            {data.has_resume && (
              <div style={{ marginTop: "var(--space-md)" }}>
                <Button variant="secondary" size="sm" icon={<Download size={14} />} loading={downloading} onClick={handleDownload}>
                  {t("portal.detail.downloadResume")}
                </Button>
              </div>
            )}
          </Card>
        </div>
      </div>
    </div>
  );
}
