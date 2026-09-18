import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ArrowLeft, Edit3, Trash2, Plus, Sparkles } from "lucide-react";
import {
  fetchJob,
  fetchApplicationForm,
  updateApplicationForm,
  publishApplicationForm,
  deleteJob as deleteJobApi,
} from "../../services/jobsService";
import { fetchCandidatesByJob } from "../../services/workersService";
import { formatDate } from "../../utils/date";
import { buildDefaultApplicationFields, validateApplicationFields } from "../../utils/applicationFields";
import PageHeader from "../../components/ui/PageHeader";
import Button from "../../components/ui/Button";
import Card from "../../components/ui/Card";
import EmptyState from "../../components/ui/EmptyState";
import StatusBadge from "../../components/ui/StatusBadge";
import ConfirmDialog from "../../components/ui/ConfirmDialog";
import Table from "../../components/ui/Table";
import JobAIAnalysisCard from "../../components/jobs/JobAIAnalysisCard";
import ApplicationFormBuilder from "../../components/application-form/ApplicationFormBuilder";
import ApplicationLinkCard from "../../components/application-form/ApplicationLinkCard";
import { useLanguage } from "../../contexts/LanguageContext";
import { useNotify } from "../../contexts/ToastContext";
import { ApiError, getErrorMessage } from "../../utils/apiError";
import type { JobInput, JobAnalytics } from "../../types/job";
import type { ApplicationFormConfig, ApplicationFieldDef } from "../../types/applicationForm";
import type { Candidate } from "../../types/worker";

const SOURCE_LABELS: Record<string, string> = {
  manual: "Manual input",
  file: "Requirement file",
  both: "Manual + file",
};

/** /jobs/:id — overview, requirement source, AI analysis, form, candidates. */
export default function JobDetailsPage() {
  const { t } = useLanguage();
  const notify = useNotify();
  const navigate = useNavigate();
  const params = useParams();
  const id = Number(params.id);

  const [job, setJob] = useState<JobInput | null>(null);
  const [jobCandidates, setJobCandidates] = useState<Candidate[]>([]);
  const [appFormConfig, setAppFormConfig] = useState<ApplicationFormConfig | null>(null);
  const [appFormLoading, setAppFormLoading] = useState(true);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [confirmDeleteJob, setConfirmDeleteJob] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [regenerating, setRegenerating] = useState(false);
  const [creatingForm, setCreatingForm] = useState(false);
  const [formSaveError, setFormSaveError] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;
    async function loadData() {
      setLoading(true);
      setError(null);
      try {
        const [jobData, candidatesData] = await Promise.all([
          fetchJob(id),
          fetchCandidatesByJob(id),
        ]);
        if (mounted) {
          setJob(jobData);
          setJobCandidates(candidatesData);
        }
      } catch (err) {
        if (mounted) {
          if (err instanceof ApiError && err.status === 404) {
            setError("not_found");
          } else if (err instanceof ApiError) {
            setError(err.message);
          } else {
            setError(t("errors.loadMessage") || "Failed to load job details. Please try again.");
          }
        }
      } finally {
        if (mounted) setLoading(false);
      }
      try {
        const formConfig = await fetchApplicationForm(id);
        if (mounted) setAppFormConfig(formConfig);
      } catch {
        // No form yet
      } finally {
        if (mounted) setAppFormLoading(false);
      }
    }
    loadData();
    return () => {
      mounted = false;
    };
  }, [id, t]);

  const analytics = useMemo(() => {
    const counts: JobAnalytics = {
      total: jobCandidates.length,
      strong_hires: 0,
      hires: 0,
      weak_hires: 0,
      do_not_hires: 0,
    };
    for (const candidate of jobCandidates) {
      counts[
        candidate.hiring_status === "strong_hire"
          ? "strong_hires"
          : candidate.hiring_status === "hire"
            ? "hires"
            : candidate.hiring_status === "weak_hire"
              ? "weak_hires"
              : "do_not_hires"
      ] += 1;
    }
    return counts;
  }, [jobCandidates]);

  const formProblems = useMemo(() => {
    const local = appFormConfig
      ? validateApplicationFields(appFormConfig.fields)
      : [];
    return formSaveError ? [formSaveError, ...local] : local;
  }, [appFormConfig, formSaveError]);

  if (loading) {
    return (
      <div className="page">
        <PageHeader title={t("pages.jobDetails") || "Job Details"} description={t("common.loading") || "Loading…"} />
        <Card>
          <div className="loading-state">{t("common.loading") || "Loading job details…"}</div>
        </Card>
      </div>
    );
  }

  if (error === "not_found" || !job) {
    return (
      <div className="page">
        <PageHeader title={t("labels.notFoundTitle") || "Job not found"} description={t("errors.notFoundMessage") || "This job may have been removed."} />
        <Card>
          <EmptyState
            tone="error"
            title={t("labels.notFoundTitle") || "Job not found"}
            message={t("errors.notFoundMessage") || "The job you are looking for may have been deleted."}
            action={
              <Button to="/jobs" icon={<ArrowLeft size={16} />}>
                {t("common.back") || "Back to jobs"}
              </Button>
            }
          />
        </Card>
      </div>
    );
  }

  if (error) {
    return (
      <div className="page">
        <PageHeader title={t("common.error") || "Error"} description={t("errors.loadMessage") || "Failed to load job details."} />
        <Card>
          <div className="error-center">
            <p>{error}</p>
            <Button onClick={() => window.location.reload()}>{t("common.retry") || "Retry"}</Button>
          </div>
        </Card>
      </div>
    );
  }

  async function handleDeleteJob() {
    setDeleting(true);
    try {
      await deleteJobApi(id);
      notify.success(t("toast.jobDeleted") || "Job deleted successfully");
      navigate("/jobs");
    } catch (err) {
      const msg = getErrorMessage(err);
      notify.error(t("toast.deleteFailed") || "Failed to delete job", msg);
      setDeleting(false);
      setConfirmDeleteJob(false);
    }
  }

  async function handleFormFieldsChange(nextFields: ApplicationFieldDef[]) {
    if (!appFormConfig) return;
    setAppFormConfig({ ...appFormConfig, fields: nextFields });
    setFormSaveError(null);
    if (validateApplicationFields(nextFields).length > 0) return;
    try {
      const updated = await updateApplicationForm(id, nextFields);
      setAppFormConfig(updated);
      notify.success(t("toast.settingsSaved") || "Application form saved");
    } catch (err) {
      setFormSaveError(
        getErrorMessage(err, "Failed to save the application form. Please try again.")
      );
    }
  }

  async function handleCreateForm() {
    setCreatingForm(true);
    setFormSaveError(null);
    try {
      const created = await updateApplicationForm(
        id,
        buildDefaultApplicationFields()
      );
      setAppFormConfig(created);
      notify.success(t("toast.jobCreated") || "Application form created");
    } catch (err) {
      setFormSaveError(
        getErrorMessage(err, "Failed to create the application form. Please try again.")
      );
    } finally {
      setCreatingForm(false);
    }
  }

  async function handleRegenerateLink() {
    setRegenerating(true);
    setFormSaveError(null);
    try {
      const updated = await publishApplicationForm(id, true);
      setAppFormConfig(updated);
      notify.success(t("toast.settingsSaved") || "Application link regenerated");
    } catch (err) {
      setFormSaveError(
        getErrorMessage(err, "Failed to regenerate the application link. Please try again.")
      );
    } finally {
      setRegenerating(false);
    }
  }

  return (
    <div className="page">
      <PageHeader
        title={job.position}
        description={`${job.company_name} · ${job.leads_count} ${t("jobs.leads") || "leads"} · ${t("jobs.created") || "Created"} ${formatDate(job.created_at)}`}
        action={
          <>
            <Button variant="secondary" to={`/jobs/${job.id}/edit`} icon={<Edit3 size={15} />}>
              {t("common.edit") || "Edit"}
            </Button>
            <Button variant="danger" onClick={() => setConfirmDeleteJob(true)} disabled={deleting} icon={<Trash2 size={15} />}>
              {t("common.delete") || "Delete"}
            </Button>
          </>
        }
      />

      <div className="job-summary-grid">
        <Card title={t("jobs.details") || "Job information"}>
          <dl className="detail-list">
            <dt>{t("jobs.company") || "Company"}</dt>
            <dd>{job.company_name}</dd>
            <dt>{t("jobs.position") || "Position"}</dt>
            <dd>{job.position}</dd>
            <dt>{t("jobs.experience") || "Required experience"}</dt>
            <dd>{job.required_experience || "—"}</dd>
            <dt>{t("jobs.skills") || "Required skills"}</dt>
            <dd>{job.required_skills || "—"}</dd>
          </dl>
          <p className="detail-description">{job.description || (t("common.noData") || "No description provided.")}</p>
        </Card>

        <Card title="Candidate summary">
          <ul className="summary-list">
            <li><span>{t("candidates.total") || "Total candidates"}</span><strong>{analytics.total}</strong></li>
            <li className="success"><span>{t("statusMeta.hiring.strong_hire") || "Strong hires"}</span><strong>{analytics.strong_hires}</strong></li>
            <li className="info"><span>{t("statusMeta.hiring.hire") || "Hires"}</span><strong>{analytics.hires}</strong></li>
            <li className="warning"><span>{t("statusMeta.hiring.weak_hire") || "Weak hires"}</span><strong>{analytics.weak_hires}</strong></li>
            <li className="danger"><span>{t("statusMeta.hiring.do_not_hire") || "Do not hire"}</span><strong>{analytics.do_not_hires}</strong></li>
          </ul>
        </Card>
      </div>

      <Card title={t("jobs.requirementSource") || "Requirement source"} subtitle="How this vacancy was created.">
        <div className="chip-row">
          <span className="chip chip--info">
            {SOURCE_LABELS[job.requirement_source ?? "manual"]}
          </span>
          {job.requirement_file_name && (
            <span className="chip">File: {job.requirement_file_name}</span>
          )}
        </div>
        {job.ai_instructions ? (
          <p className="detail-description">AI instructions: {job.ai_instructions}</p>
        ) : (
          <p className="muted-note">No extra AI instructions were provided.</p>
        )}
      </Card>

      {job.ai_analysis ? (
        <JobAIAnalysisCard analysis={job.ai_analysis} />
      ) : (
        <Card title={t("jobs.aiAnalysis") || "AI Vacancy Analysis"} subtitle="No AI analysis for this vacancy yet.">
          <EmptyState
            title={t("jobs.noAiAnalysis") || "No AI analysis yet"}
            message="Jobs created with the AI flow include a structured vacancy analysis."
            action={<Button to="/jobs/create" icon={<Sparkles size={16} />}>{t("jobs.createWithAi") || "Create with AI"}</Button>}
          />
        </Card>
      )}

      {/* Public application form builder */}
      {appFormLoading ? (
        <Card><p className="muted-note">{t("common.loading") || "Loading application form…"}</p></Card>
      ) : appFormConfig ? (
        <>
          <ApplicationLinkCard
            token={appFormConfig.public_token}
            jobTitle={job?.position || undefined}
            onRegenerate={handleRegenerateLink}
            regenerating={regenerating}
          />
          <ApplicationFormBuilder
            fields={appFormConfig.fields}
            errors={formProblems}
            onFieldsChange={handleFormFieldsChange}
          />
        </>
      ) : (
        <Card>
          <EmptyState
            title={t("jobs.noFormYet") || "No application form yet"}
            message="Start from the standard question set and customize each field right here."
            action={
              <Button onClick={handleCreateForm} loading={creatingForm} disabled={creatingForm} icon={<Plus size={16} />}>
                {creatingForm ? (t("common.loading") || "Creating…") : (t("jobs.createForm") || "Create application form")}
              </Button>
            }
          />
          {formSaveError && (
            <p className="field-error" role="alert">
              {formSaveError}
            </p>
          )}
        </Card>
      )}

      <Card title={t("nav.applications") || "Applications for this job"} subtitle="AI-screened submissions.">
        {jobCandidates.length === 0 ? (
          <EmptyState
            title={t("empty.applicationsTitle") || "No applications yet"}
            message={t("empty.applicationsMessage") || "Applications will appear here when candidates apply."}
          />
        ) : (
          <Table
            rows={jobCandidates}
            rowKey={(application) => application.id}
            columns={[
              {
                header: t("candidates.name") || "Candidate",
                render: (application) => (
                  <div>
                    <Link
                      className="table-primary"
                      to={`/candidates/${application.id}`}
                    >
                      {application.name}
                    </Link>
                    <div className="table-secondary">{application.email}</div>
                  </div>
                ),
              },
              {
                header: t("candidates.aiScore") || "AI score",
                render: (application) => (
                  <span className="table-number">
                    {Math.round(application.ai_score)}%
                  </span>
                ),
              },
              {
                header: t("labels.status") || "Hiring status",
                render: (application) => (
                  <StatusBadge kind="hiring" value={application.hiring_status} />
                ),
              },
              {
                header: t("applications.submittedAt") || "Submitted",
                render: (application) => formatDate(application.submitted_at),
              },
            ]}
          />
        )}
      </Card>

      <ConfirmDialog
        open={confirmDeleteJob}
        title={t("jobs.deleteConfirm") || "Delete this job?"}
        message={`This will permanently remove "${job.position}" at ${job.company_name} and all its candidates.`}
        confirmLabel={t("jobs.deleteJobBtn") || "Delete"}
        onConfirm={handleDeleteJob}
        onCancel={() => setConfirmDeleteJob(false)}
        disabled={deleting}
      />
    </div>
  );
}