import { useEffect, useState, type CSSProperties } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ArrowLeft, FileText, CheckCircle2, AlertCircle, Trash2 } from "lucide-react";
import {
  getWorker,
  updateWorker,
  deleteWorker,
} from "../../services/workersService";
import { formatDate } from "../../utils/date";
import PageHeader from "../../components/ui/PageHeader";
import Button from "../../components/ui/Button";
import Card from "../../components/ui/Card";
import EmptyState from "../../components/ui/EmptyState";
import StatusBadge from "../../components/ui/StatusBadge";
import ApplicationStatusBadge from "../../components/ui/ApplicationStatusBadge";
import Select from "../../components/forms/Select";
import ConfirmDialog from "../../components/ui/ConfirmDialog";
import { useLanguage } from "../../contexts/LanguageContext";
import { useNotify } from "../../contexts/ToastContext";
import type {
  CandidateDetail,
  HiringStatus,
  InterviewStatus,
} from "../../types/worker";

/** /candidates/:id — candidate profile, interview progress, and stored AI screening. */
export default function CandidateDetailsPage() {
  const { t } = useLanguage();
  const notify = useNotify();
  const params = useParams();
  const navigate = useNavigate();
  const id = Number(params.id);

  const [candidate, setCandidate] = useState<CandidateDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  const interviewOptions: { value: InterviewStatus; label: string }[] = [
    { value: "not_completed", label: t("statusMeta.interview.not_completed") || "Not completed" },
    { value: "in_process", label: t("statusMeta.interview.in_process") || "In process" },
    { value: "completed", label: t("statusMeta.interview.completed") || "Completed" },
  ];

  const hiringOptions: { value: HiringStatus; label: string }[] = [
    { value: "strong_hire", label: t("statusMeta.hiring.strong_hire") || "Strong Hire" },
    { value: "hire", label: t("statusMeta.hiring.hire") || "Hire" },
    { value: "weak_hire", label: t("statusMeta.hiring.weak_hire") || "Weak Hire" },
    { value: "do_not_hire", label: t("statusMeta.hiring.do_not_hire") || "Do Not Hire" },
  ];

  useEffect(() => {
    let cancelled = false;
    async function loadCandidate() {
      setLoading(true);
      setError(null);
      try {
        const data = await getWorker(id);
        if (!cancelled) setCandidate(data);
      } catch (err: unknown) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : t("errors.notFoundMessage") || "Candidate not found");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    loadCandidate();
    return () => {
      cancelled = true;
    };
  }, [id, t]);

  const setHiringDecision = async (status: HiringStatus) => {
    if (!candidate) return;
    try {
      const updated = await updateWorker(candidate.id, { hiring_status: status });
      setCandidate(updated);
      notify.success(t("toast.statusUpdated") || "Hiring decision updated");
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : t("toast.saveFailed") || "Failed to update hiring status";
      setActionError(msg);
      notify.error(t("toast.saveFailed") || "Failed", msg);
    }
  };

  const setInterviewStatus = async (status: InterviewStatus) => {
    if (!candidate) return;
    try {
      const updated = await updateWorker(candidate.id, { interview_status: status });
      setCandidate(updated);
      notify.success(t("toast.statusUpdated") || "Interview status updated");
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : t("toast.saveFailed") || "Failed to update interview status";
      setActionError(msg);
      notify.error(t("toast.saveFailed") || "Failed", msg);
    }
  };

  const handleDelete = async () => {
    if (!candidate) return;
    try {
      await deleteWorker(candidate.id);
      notify.success(t("toast.jobDeleted") || "Candidate removed");
      navigate("/candidates");
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : t("toast.deleteFailed") || "Failed to remove candidate";
      setActionError(msg);
      notify.error(t("toast.deleteFailed") || "Failed", msg);
    }
  };

  if (loading) {
    return (
      <div className="page">
        <PageHeader title={t("pages.candidateDetails") || "Candidate Details"} description={t("common.loading") || "Loading candidate…"} />
        <Card>
          <div className="loading-state">{t("common.loading") || "Loading candidate details…"}</div>
        </Card>
      </div>
    );
  }

  if (error || !candidate) {
    return (
      <div className="page">
        <PageHeader title={t("labels.notFoundTitle") || "Candidate not found"} description={t("errors.notFoundMessage") || "This candidate may have been removed."} />
        <Card>
          <EmptyState
            tone="error"
            title={t("labels.notFoundTitle") || "Candidate not found"}
            message={error || (t("errors.notFoundMessage") || "The candidate you are looking for may have been deleted.")}
            action={
              <Button to="/candidates" icon={<ArrowLeft size={16} />}>
                {t("common.back") || "Back to candidates"}
              </Button>
            }
          />
        </Card>
      </div>
    );
  }

  const analysis = candidate.analysis;
  const matchScore = Math.round(candidate.ai_score || (analysis?.match_percentage ?? 0));

  return (
    <div className="page">
      <div className="candidate-hero">
        <PageHeader
          title={candidate.name}
          description={`${candidate.position ? `${candidate.position} · ${candidate.company_name}` : candidate.email}`}
        />
        <div className="candidate-hero-badges">
          <StatusBadge kind="hiring" value={candidate.hiring_status} />
          <StatusBadge kind="interview" value={candidate.interview_status} />
          <Button variant="secondary" to={`/applications/${candidate.id}`}>
            {t("candidates.viewApplication") || "View Application"}
          </Button>
          <Button variant="danger" onClick={() => setConfirmDelete(true)} icon={<Trash2 size={16} />}>
            {t("common.delete") || "Remove"}
          </Button>
        </div>
      </div>

      {actionError && (
        <div className="notice notice--danger" style={{ marginBottom: "1.5rem" }}>
          {actionError}
        </div>
      )}

      <div className="candidate-grid">
        {/* Candidate Info */}
        <Card title={t("candidates.info") || "Candidate Information"}>
          <dl className="detail-list">
            <dt>{t("auth.name") || "Full name"}</dt>
            <dd>{candidate.name}</dd>
            <dt>{t("auth.email") || "Email"}</dt>
            <dd>{candidate.email}</dd>
            <dt>{t("jobs.position") || "Applied position"}</dt>
            <dd>{candidate.position || "—"}</dd>
            <dt>{t("jobs.company") || "Company"}</dt>
            <dd>{candidate.company_name || "—"}</dd>
            <dt>{t("labels.status") || "Application Stage"}</dt>
            <dd>
              <ApplicationStatusBadge value={candidate.application_status} />
            </dd>
            <dt>{t("candidates.appliedDate") || "Candidate Since"}</dt>
            <dd>{formatDate(candidate.candidate_at || candidate.created_at)}</dd>
          </dl>
        </Card>

        {/* Manual HR Hiring Decision */}
        <Card title={t("candidates.hiringDecision") || "HR Hiring Decision"}>
          <div className="recommendation" style={{ marginBottom: "1rem" }}>
            <StatusBadge kind="hiring" value={candidate.hiring_status} />
          </div>
          <Select
            label={t("candidates.setDecision") || "Set Hiring Decision"}
            value={candidate.hiring_status}
            onChange={(v) => setHiringDecision(v as HiringStatus)}
            options={hiringOptions}
          />
        </Card>

        {/* Manual Interview Status & Progress */}
        <Card
          title={t("candidates.interviewProgress") || "Interview Progress"}
          action={
            <Link to="/interviews" className="btn btn--secondary btn--sm">
              {t("nav.interviews") || "Manage Interviews"}
            </Link>
          }
        >
          <p className="muted-note" style={{ marginBottom: "1rem" }}>
            {t("interviews.description") || "Interviews are manually scheduled and evaluated by HR."}
          </p>
          <fieldset className="radio-list">
            <legend className="sr-only">Interview status</legend>
            {interviewOptions.map((option) => (
              <label key={option.value} className="radio-option">
                <input
                  type="radio"
                  name="interview-status"
                  value={option.value}
                  checked={candidate.interview_status === option.value}
                  onChange={() => setInterviewStatus(option.value)}
                />
                <span>{option.label}</span>
              </label>
            ))}
          </fieldset>

          {candidate.interviews && candidate.interviews.length > 0 && (
            <div style={{ marginTop: "1.5rem" }}>
              <h4 className="mini-heading">{t("interviews.title") || "Scheduled Rounds"}</h4>
              <ul className="bar-list">
                {candidate.interviews.map((iv) => (
                  <li key={iv.id} className="bar-item">
                    <span className="bar-label">{iv.interviewer}</span>
                    <span className="bar-value">{formatDate(iv.scheduled_at)}</span>
                    {iv.notes && <p className="table-secondary" style={{ width: "100%", marginTop: "0.25rem" }}>Notes: {iv.notes}</p>}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </Card>
      </div>

      {/* Submitted Dynamic Form Responses */}
      {candidate.responses && candidate.responses.length > 0 && (
        <Card title={t("applications.submittedAnswers") || "Submitted Application Answers"} subtitle="Answers provided during public application submission.">
          <dl className="detail-list">
            {candidate.responses.map((resp, idx) => (
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

      {/* Saved AI Resume Analysis */}
      <Card title={t("candidates.aiScreening") || "Stored AI Screening Analysis"} subtitle="AI match analysis saved from candidate submission.">
        {!analysis ? (
          <EmptyState
            title={t("applications.noAnalysis") || "No AI analysis recorded"}
            message="Visit the Application Details page to run or inspect AI analysis."
            action={
              <Link to={`/applications/${candidate.id}`} className="btn btn--primary">
                {t("candidates.viewApplication") || "Go to Application"}
              </Link>
            }
          />
        ) : (
          <div className="analysis">
            <div className="analysis-score">
              <div
                className="analysis-score-ring"
                style={{ "--score": `${matchScore * 3.6}deg` } as CSSProperties}
              >
                <span>{matchScore}%</span>
              </div>
              <div>
                <h3>{t("candidates.matchScore") || "Match Score"}</h3>
                <p>{t("candidates.matchSubtitle") || "Calculated against job requirements"}</p>
                {analysis.model && (
                  <span className="badge badge--neutral" style={{ marginTop: "0.25rem" }}>
                    Model: {analysis.model}
                  </span>
                )}
              </div>
            </div>

            {analysis.summary && (
              <div style={{ marginBottom: "1.5rem" }}>
                <h4 className="mini-heading">{t("applications.summary") || "Summary"}</h4>
                <p className="analysis-summary">{analysis.summary}</p>
              </div>
            )}

            <div className="analysis-skills" style={{ marginBottom: "1.5rem" }}>
              <div>
                <h4>{t("candidates.matchedSkills") || "Matched Skills & Requirements"}</h4>
                {analysis.matched_skills?.length === 0 ? (
                  <p className="muted-note">{t("common.noData") || "None recorded."}</p>
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
                <h4>{t("candidates.missingSkills") || "Missing Skills & Requirements"}</h4>
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

            {(analysis.strengths?.length > 0 || analysis.weaknesses?.length > 0) && (
              <div className="candidate-grid" style={{ marginBottom: "1.5rem" }}>
                {analysis.strengths?.length > 0 && (
                  <div>
                    <h4 className="mini-heading">{t("candidates.strengths") || "Key Strengths"}</h4>
                    <ul className="skill-list">
                      {analysis.strengths.map((s, idx) => (
                        <li key={idx} className="skill-match">+ {s}</li>
                      ))}
                    </ul>
                  </div>
                )}
                {analysis.weaknesses?.length > 0 && (
                  <div>
                    <h4 className="mini-heading">{t("candidates.weaknesses") || "Potential Weaknesses / Gaps"}</h4>
                    <ul className="skill-list">
                      {analysis.weaknesses.map((w, idx) => (
                        <li key={idx} className="skill-missing">! {w}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            )}

            {(analysis.experience_analysis || analysis.education_analysis) && (
              <div className="candidate-grid">
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

      {/* Resume Card */}
      <Card
        title={t("candidates.resume") || "Resume"}
        subtitle={candidate.resume_path ? candidate.resume_path.split("/").pop() : "No file uploaded"}
        action={
          candidate.resume_url ? (
            <a
              href={candidate.resume_url}
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
          <h3>{candidate.name}</h3>
          <p className="resume-preview-contact">{candidate.email}</p>
          <p className="resume-preview-blurb">
            {candidate.resume_path
              ? `Stored resume path: ${candidate.resume_path}`
              : "No resume file attached."}
          </p>
        </div>
      </Card>

      <ConfirmDialog
        open={confirmDelete}
        title={t("common.delete") || "Remove this candidate?"}
        message="This action will permanently remove the candidate from the pipeline."
        confirmLabel={t("common.delete") || "Remove"}
        onConfirm={handleDelete}
        onCancel={() => setConfirmDelete(false)}
      />
    </div>
  );
}