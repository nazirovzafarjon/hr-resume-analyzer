import { useEffect, useState, type CSSProperties } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { ArrowLeft, Sparkles, UserPlus, Trash2, FileText, CheckCircle2, AlertCircle, RefreshCw } from "lucide-react";
import {
  getWorker,
  updateWorker,
  analyzeWorker,
  convertToCandidate,
  deleteWorker,
} from "../../services/workersService";
import { formatDate } from "../../utils/date";
import PageHeader from "../../components/ui/PageHeader";
import PageMeta from "../../components/seo/PageMeta";
import Button from "../../components/ui/Button";
import Card from "../../components/ui/Card";
import EmptyState from "../../components/ui/EmptyState";
import ApplicationStatusBadge, {
  AnalysisStatusBadge,
} from "../../components/ui/ApplicationStatusBadge";
import StatusBadge from "../../components/ui/StatusBadge";
import Select from "../../components/forms/Select";
import ConfirmDialog from "../../components/ui/ConfirmDialog";
import { Skeleton, SkeletonText } from "../../components/ui/Skeleton";
import { useLanguage } from "../../contexts/LanguageContext";
import { useNotify } from "../../contexts/ToastContext";
import type {
  CandidateDetail,
  ApplicationStatus,
} from "../../types/worker";

/** /applications/:id — single submitted application with AI analysis and candidate pipeline actions. */
export default function ApplicationDetailsPage() {
  const { t } = useLanguage();
  const notify = useNotify();
  const params = useParams();
  const navigate = useNavigate();
  const id = Number(params.id);

  const [application, setApplication] = useState<CandidateDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [converting, setConverting] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  const appStatusOptions: { value: ApplicationStatus; label: string }[] = [
    { value: "new", label: t("statusMeta.application.new") || "New" },
    { value: "reviewing", label: t("statusMeta.application.reviewing") || "Reviewing" },
    { value: "shortlisted", label: t("statusMeta.application.shortlisted") || "Shortlisted" },
    { value: "interview", label: t("statusMeta.application.interview") || "Interview" },
    { value: "rejected", label: t("statusMeta.application.rejected") || "Rejected" },
    { value: "withdrawn", label: t("statusMeta.application.withdrawn") || "Withdrawn" },
  ];

  const aiRecommendationLabels: Record<string, { label: string; desc: string }> = {
    strong_hire: {
      label: t("statusMeta.hiring.strong_hire") || "Strong Hire",
      desc: "Excellently aligned with job requirements and strong skill coverage.",
    },
    hire: {
      label: t("statusMeta.hiring.hire") || "Hire",
      desc: "Meets the core requirements for this position.",
    },
    weak_hire: {
      label: t("statusMeta.hiring.weak_hire") || "Weak Hire",
      desc: "Partial alignment; check missing skills or experience gaps before deciding.",
    },
    do_not_hire: {
      label: t("statusMeta.hiring.do_not_hire") || "Do Not Hire",
      desc: "Does not meet the critical requirements for this role.",
    },
  };

  useEffect(() => {
    let cancelled = false;
    async function loadWorker() {
      setLoading(true);
      setError(null);
      try {
        const data = await getWorker(id);
        if (!cancelled) setApplication(data);
      } catch (err: unknown) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : t("errors.notFoundMessage") || "Application not found");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    loadWorker();
    return () => {
      cancelled = true;
    };
  }, [id, t]);

  const handleStatusChange = async (newStatus: string) => {
    if (!application) return;
    try {
      const updated = await updateWorker(application.id, {
        application_status: newStatus as ApplicationStatus,
      });
      setApplication(updated);
      notify.success(t("toast.statusUpdated") || "Status updated");
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : t("toast.saveFailed") || "Failed to update status";
      setActionError(msg);
      notify.error(t("toast.saveFailed") || "Failed", msg);
    }
  };

  const handleRunAnalysis = async (force = false) => {
    if (!application) return;
    setAnalyzing(true);
    setActionError(null);
    notify.info(t("toast.analysisStarted") || "AI analysis started");
    try {
      const updated = await analyzeWorker(application.id, force);
      setApplication(updated);
      notify.success(t("toast.analysisComplete") || "AI analysis complete");
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : t("toast.analysisFailed") || "AI analysis failed";
      setActionError(msg);
      notify.error(t("toast.analysisFailed") || "AI analysis failed", msg);
    } finally {
      setAnalyzing(false);
    }
  };

  const handleConvertToCandidate = async () => {
    if (!application) return;
    setConverting(true);
    setActionError(null);
    try {
      const updated = await convertToCandidate(application.id);
      setApplication(updated);
      notify.success(t("toast.statusUpdated") || "Moved to candidate pipeline");
      navigate(`/candidates/${application.id}`);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : t("toast.saveFailed") || "Failed to move to candidates";
      setActionError(msg);
      notify.error(t("toast.saveFailed") || "Failed", msg);
      setConverting(false);
    }
  };

  const handleDelete = async () => {
    if (!application) return;
    try {
      await deleteWorker(application.id);
      notify.success(t("toast.jobDeleted") || "Application deleted");
      navigate("/applications");
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : t("toast.deleteFailed") || "Failed to delete application";
      setActionError(msg);
      notify.error(t("toast.deleteFailed") || "Failed", msg);
    }
  };

  if (loading) {
    return (
      <div className="page">
        <PageHeader title={t("pages.applicationDetails") || "Application Details"} description={t("common.loading") || "Loading submission…"} />
        <Card>
          <Skeleton variant="title" />
          <SkeletonText lines={3} />
        </Card>
      </div>
    );
  }

  if (error || !application) {
    return (
      <div className="page">
        <PageHeader title={t("labels.notFoundTitle") || "Application not found"} description={t("errors.notFoundMessage") || "It may have been removed."} />
        <Card>
          <EmptyState
            tone="error"
            title={t("labels.notFoundTitle") || "Application not found"}
            message={error || (t("errors.notFoundMessage") || "The application you are looking for does not exist.")}
            action={
              <Button to="/applications" icon={<ArrowLeft size={16} />}>
                {t("common.back") || "Back to applications"}
              </Button>
            }
          />
        </Card>
      </div>
    );
  }

  const analysis = application.analysis;
  const matchPercentage = Math.round(application.ai_score || (analysis?.match_percentage ?? 0));
  const aiRec = analysis?.ai_recommendation
    ? aiRecommendationLabels[analysis.ai_recommendation]
    : null;

  return (
    <div className="page">
      <PageMeta title={application.name} noindex />
      <div className="candidate-hero">
        <PageHeader
          title={application.name}
          description={`${application.position ? `${application.position} · ${application.company_name}` : application.email} · ${t("applications.submittedAt") || "Submitted"} ${formatDate(application.submitted_at || application.created_at)}`}
        />
        <div className="candidate-hero-badges">
          <ApplicationStatusBadge value={application.application_status} />
          <AnalysisStatusBadge value={application.analysis_status} />
          {application.is_candidate ? (
            <Button variant="primary" to={`/candidates/${application.id}`}>
              {t("candidates.viewProfile") || "View Candidate Profile →"}
            </Button>
          ) : (
            <Button
              variant="primary"
              onClick={handleConvertToCandidate}
              disabled={converting}
              icon={<UserPlus size={16} />}
            >
              {converting ? (t("common.loading") || "Moving…") : (t("applications.moveToCandidate") || "Move to Candidate Pipeline")}
            </Button>
          )}
          <Button variant="danger" onClick={() => setConfirmDelete(true)} icon={<Trash2 size={16} />}>
            {t("common.delete") || "Delete"}
          </Button>
        </div>
      </div>

      {actionError && (
        <div className="alert alert--error" style={{ marginBottom: "1.5rem" }}>
          {actionError}
        </div>
      )}

      {application.analysis_status === "failed" && (
        <div className="alert alert--warning" style={{ marginBottom: "1.5rem" }}>
          <strong>{t("toast.analysisFailed") || "AI Analysis Failed"}:</strong> {application.analysis_error || "Unknown error occurred."}
          <div style={{ marginTop: "0.5rem" }}>
            <Button
              variant="secondary"
              onClick={() => handleRunAnalysis(true)}
              disabled={analyzing}
              icon={<RefreshCw size={14} />}
            >
              {analyzing ? (t("common.loading") || "Retrying…") : (t("common.retry") || "Retry AI Analysis")}
            </Button>
          </div>
        </div>
      )}

      <div className="candidate-grid">
        {/* Applicant Details */}
        <Card title={t("applications.applicantInfo") || "Applicant Information"}>
          <dl className="detail-list">
            <dt>{t("auth.name") || "Full name"}</dt>
            <dd>{application.name}</dd>
            <dt>{t("auth.email") || "Email"}</dt>
            <dd>{application.email}</dd>
            <dt>{t("jobs.position") || "Applied Position"}</dt>
            <dd>{application.position || "—"}</dd>
            <dt>{t("jobs.company") || "Company"}</dt>
            <dd>{application.company_name || "—"}</dd>
            <dt>{t("applications.submittedAt") || "Submitted Date"}</dt>
            <dd>{formatDate(application.submitted_at || application.created_at)}</dd>
            <dt>{t("candidates.pipelineStatus") || "Candidate Status"}</dt>
            <dd>
              {application.is_candidate ? (
                <span className="badge badge--success">{t("candidates.inPipeline") || "In Candidate Pipeline"}</span>
              ) : (
                <span className="badge badge--neutral">{t("candidates.applicationStage") || "Application Stage"}</span>
              )}
            </dd>
          </dl>
        </Card>

        {/* Pipeline & HR Controls */}
        <Card title={t("applications.hrReview") || "HR Application Review"}>
          <p className="muted-note" style={{ marginBottom: "1rem" }}>
            {t("applications.hrReviewNote") || "Application pipeline status is fully controlled by HR."}
          </p>
          <Select
            label={t("labels.status") || "Application Status"}
            value={application.application_status}
            onChange={handleStatusChange}
            options={appStatusOptions}
          />
          <div style={{ marginTop: "1.5rem" }}>
            <Button
              variant="secondary"
              onClick={() => handleRunAnalysis(true)}
              disabled={analyzing}
              icon={<Sparkles size={15} />}
            >
              {analyzing
                ? (t("common.loading") || "Running AI Analysis…")
                : application.analysis_status === "completed"
                  ? (t("applications.reAnalyze") || "Re-analyze with AI")
                  : (t("applications.runAnalysis") || "Run AI Analysis")}
            </Button>
          </div>
        </Card>
      </div>

      {/* Dynamic Form Responses */}
      {application.responses && application.responses.length > 0 && (
        <Card title={t("applications.submittedAnswers") || "Submitted Application Answers"} subtitle="Responses entered by the applicant in the public application form.">
          <dl className="detail-list">
            {application.responses.map((resp, idx) => (
              <div key={resp.field_id || idx} style={{ marginBottom: "0.75rem" }}>
                <dt>{resp.label || resp.key || "Question"}</dt>
                <dd style={{ marginTop: "0.25rem" }}>
                  {typeof resp.value === "boolean"
                    ? resp.value
                      ? "Yes"
                      : "No"
                    : Array.isArray(resp.value)
                      ? resp.value.join(", ")
                      : String(resp.value ?? "—")}
                </dd>
              </div>
            ))}
          </dl>
        </Card>
      )}

      {/* AI Analysis Section */}
      <Card
        title={t("applications.aiAnalysisTitle")}
        subtitle={t("applications.aiAnalysisSubtitle")}
        action={
          application.analysis_status !== "analyzing" ? (
            <Button
              variant="secondary"
              onClick={() => handleRunAnalysis(true)}
              disabled={analyzing}
              icon={<RefreshCw size={14} />}
            >
              {analyzing ? (t("common.loading") || "Analyzing…") : (t("applications.refreshAnalysis") || "Refresh Analysis")}
            </Button>
          ) : undefined
        }
      >
        {application.analysis_status === "analyzing" || analyzing ? (
          <div className="loading-state">
            <Sparkles size={18} style={{ marginRight: "8px", verticalAlign: "middle", animation: "spin 2s linear infinite" }} />
            {t("applications.analyzing") || "Analyzing resume against job requirements…"}
          </div>
        ) : !analysis ? (
          <EmptyState
            title={t("applications.noAnalysis") || "No AI analysis yet"}
            message="Click 'Run AI Analysis' to screen this applicant against the job requirements."
            action={
              <Button
                variant="primary"
                onClick={() => handleRunAnalysis(true)}
                disabled={analyzing}
                icon={<Sparkles size={15} />}
              >
                {t("applications.runAnalysis") || "Run AI Analysis"}
              </Button>
            }
          />
        ) : (
          <div className="analysis">
            <div className="analysis-score">
              <div
                className="analysis-score-ring"
                style={{ "--score": `${matchPercentage * 3.6}deg` } as CSSProperties}
              >
                <span>{matchPercentage}%</span>
              </div>
              <div>
                <h3>{t("candidates.matchScore") || "Match Score"}</h3>
                <p>{t("candidates.matchSubtitle") || "Objective requirement alignment"}</p>
                {analysis.model && (
                  <span className="badge badge--neutral" style={{ marginTop: "0.25rem" }}>
                    Model: {analysis.model}
                  </span>
                )}
              </div>
            </div>

            {/* Advisory AI Recommendation */}
            {aiRec && (
              <div
                className="alert alert--info"
                style={{ marginTop: "1rem", marginBottom: "1.5rem" }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
                  <StatusBadge kind="hiring" value={analysis.ai_recommendation as any} />
                  <div>
                    <strong>AI Recommendation: {aiRec.label}</strong>
                    <div style={{ fontSize: "0.875rem", color: "var(--color-text-secondary)" }}>
                      {aiRec.desc}
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* Summary */}
            {analysis.summary && (
              <div style={{ marginBottom: "1.5rem" }}>
                <h4 className="mini-heading">{t("applications.summary") || "Summary"}</h4>
                <p className="analysis-summary">{analysis.summary}</p>
              </div>
            )}

            {/* Matched vs Missing Requirements */}
            <div className="analysis-skills" style={{ marginBottom: "1.5rem" }}>
              <div>
                <h4>{t("candidates.matchedRequirements") || "Matched Requirements"}</h4>
                {analysis.matched_requirements?.length === 0 ? (
                  <p className="muted-note">{t("common.noData") || "No specific requirements matched."}</p>
                ) : (
                  <ul className="skill-list">
                    {analysis.matched_requirements?.map((req, idx) => (
                      <li key={idx} className="skill-match">
                        <span aria-hidden="true"><CheckCircle2 size={14} style={{ display: "inline", verticalAlign: "middle" }} /></span> {req}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
              <div>
                <h4>{t("candidates.missingRequirements") || "Missing Requirements"}</h4>
                {analysis.missing_requirements?.length === 0 ? (
                  <p className="muted-note">All core requirements met in submission.</p>
                ) : (
                  <ul className="skill-list">
                    {analysis.missing_requirements?.map((req, idx) => (
                      <li key={idx} className="skill-missing">
                        <span aria-hidden="true"><AlertCircle size={14} style={{ display: "inline", verticalAlign: "middle" }} /></span> {req}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </div>

            {/* Matched vs Missing Skills */}
            <div className="analysis-skills" style={{ marginBottom: "1.5rem" }}>
              <div>
                <h4>{t("candidates.matchedSkills") || "Matched Skills"}</h4>
                {analysis.matched_skills?.length === 0 ? (
                  <p className="muted-note">{t("common.noData") || "None extracted."}</p>
                ) : (
                  <ul className="skill-list">
                    {analysis.matched_skills?.map((skill, idx) => (
                      <li key={idx} className="skill-match">
                        <span aria-hidden="true"><CheckCircle2 size={14} style={{ display: "inline", verticalAlign: "middle" }} /></span> {skill}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
              <div>
                <h4>{t("candidates.missingSkills") || "Missing Skills"}</h4>
                {analysis.missing_skills?.length === 0 ? (
                  <p className="muted-note">All required skills matched.</p>
                ) : (
                  <ul className="skill-list">
                    {analysis.missing_skills?.map((skill, idx) => (
                      <li key={idx} className="skill-missing">
                        <span aria-hidden="true"><AlertCircle size={14} style={{ display: "inline", verticalAlign: "middle" }} /></span> {skill}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </div>

            {/* Strengths & Weaknesses / Risks */}
            <div className="candidate-grid" style={{ marginBottom: "1.5rem" }}>
              <div>
                <h4 className="mini-heading">{t("candidates.strengths") || "Strengths"}</h4>
                {analysis.strengths?.length === 0 ? (
                  <p className="muted-note">{t("common.noData") || "No standout strengths recorded."}</p>
                ) : (
                  <ul className="skill-list">
                    {analysis.strengths?.map((s, idx) => (
                      <li key={idx} className="skill-match">
                        + {s}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
              <div>
                <h4 className="mini-heading">{t("candidates.weaknesses") || "Weaknesses / Potential Risks"}</h4>
                {analysis.weaknesses?.length === 0 && analysis.risks?.length === 0 ? (
                  <p className="muted-note">{t("common.noData") || "No specific risks or weaknesses identified."}</p>
                ) : (
                  <ul className="skill-list">
                    {analysis.weaknesses?.map((w, idx) => (
                      <li key={idx} className="skill-missing">
                        ! {w}
                      </li>
                    ))}
                    {analysis.risks?.map((r, idx) => (
                      <li key={idx} className="skill-missing">
                        ⚠ {r}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </div>

            {/* Experience & Education breakdown */}
            {(analysis.experience_analysis || analysis.education_analysis) && (
              <div className="candidate-grid" style={{ marginBottom: "1.5rem" }}>
                {analysis.experience_analysis && (
                  <div>
                    <h4 className="mini-heading">{t("candidates.experienceAnalysis") || "Experience Analysis"}</h4>
                    <p style={{ fontSize: "0.9375rem" }}>{analysis.experience_analysis}</p>
                  </div>
                )}
                {analysis.education_analysis && (
                  <div>
                    <h4 className="mini-heading">{t("candidates.educationAnalysis") || "Education Analysis"}</h4>
                    <p style={{ fontSize: "0.9375rem" }}>{analysis.education_analysis}</p>
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </Card>

      {/* Resume File Card */}
      <Card
        title={t("candidates.resume") || "Resume"}
        subtitle={application.resume_path ? application.resume_path.split("/").pop() : "No file uploaded"}
        action={
          application.resume_url ? (
            <a
              href={application.resume_url}
              target="_blank"
              rel="noopener noreferrer"
              className="btn btn--secondary"
            >
              <FileText size={15} style={{ marginRight: "4px" }} />
              {t("candidates.viewResume") || "View / Download Resume"}
            </a>
          ) : undefined
        }
      >
        <div className="resume-preview">
          <h3>{application.name}</h3>
          <p className="resume-preview-contact">{application.email}</p>
          <p className="resume-preview-blurb">
            {application.resume_path
              ? `Stored at: ${application.resume_path}`
              : "No resume file attached to this application."}
          </p>
        </div>
      </Card>

      <ConfirmDialog
        open={confirmDelete}
        title={t("common.delete") || "Delete this application?"}
        message="This action will permanently delete the application and any associated data."
        confirmLabel={t("common.delete") || "Delete"}
        onConfirm={handleDelete}
        onCancel={() => setConfirmDelete(false)}
      />
    </div>
  );
}
