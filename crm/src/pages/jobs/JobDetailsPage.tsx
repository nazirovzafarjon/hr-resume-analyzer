import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ArrowLeft, Copy, Edit3, ExternalLink, MoreHorizontal, Plus, Trash2, Users } from "lucide-react";
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
import { jobStatusFromToken } from "../../utils/statusLabels";
import { copyToClipboard } from "../../utils/clipboard";
import { applicationUrl } from "../../components/application-form/ApplicationLinkCard";
import PageHeader from "../../components/ui/PageHeader";
import PageMeta from "../../components/seo/PageMeta";
import Button from "../../components/ui/Button";
import Card from "../../components/ui/Card";
import EmptyState from "../../components/ui/EmptyState";
import ErrorState from "../../components/ui/ErrorState";
import StatusBadge from "../../components/ui/StatusBadge";
import ConfirmDialog from "../../components/ui/ConfirmDialog";
import Dropdown, { DropdownItem, DropdownSeparator } from "../../components/ui/Dropdown";
import Table from "../../components/ui/Table";
import Tabs, { TabPanel } from "../../components/ui/Tabs";
import ApplicationFormBuilder from "../../components/application-form/ApplicationFormBuilder";
import ApplicationLinkCard from "../../components/application-form/ApplicationLinkCard";
import { Skeleton, SkeletonText } from "../../components/ui/Skeleton";
import { useLanguage } from "../../contexts/LanguageContext";
import { useNotify } from "../../contexts/ToastContext";
import { ApiError, getErrorMessage } from "../../utils/apiError";
import type { JobInput, JobAnalytics } from "../../types/job";
import type { ApplicationFormConfig, ApplicationFieldDef } from "../../types/applicationForm";
import type { Candidate } from "../../types/worker";

type SaveStatus = "idle" | "saving" | "saved" | "error";

const SAVE_DEBOUNCE_MS = 700;

/** /jobs/:id — overview, AI-generated form, candidates. */
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
  const [appFormError, setAppFormError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState("overview");
  const [confirmDeleteJob, setConfirmDeleteJob] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [regenerating, setRegenerating] = useState(false);
  const [creatingForm, setCreatingForm] = useState(false);
  const [formSaveError, setFormSaveError] = useState<string | null>(null);
  const [saveStatus, setSaveStatus] = useState<SaveStatus>("idle");

  const saveTimerRef = useRef<number | null>(null);
  const savedIndicatorTimerRef = useRef<number | null>(null);

  function loadApplicationForm() {
    setAppFormLoading(true);
    setAppFormError(null);
    fetchApplicationForm(id)
      .then((formConfig) => setAppFormConfig(formConfig))
      .catch((err) => {
        if (err instanceof ApiError && err.status === 404) {
          setAppFormConfig(null); // Genuinely no form configured yet.
        } else {
          setAppFormError(getErrorMessage(err, t("errors.loadMessage")));
        }
      })
      .finally(() => setAppFormLoading(false));
  }

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
    }
    loadData();
    return () => {
      mounted = false;
    };
  }, [id]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    loadApplicationForm();
    return () => {
      if (saveTimerRef.current) window.clearTimeout(saveTimerRef.current);
      if (savedIndicatorTimerRef.current) window.clearTimeout(savedIndicatorTimerRef.current);
    };
  }, [id]); // eslint-disable-line react-hooks/exhaustive-deps

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
          <Skeleton variant="title" />
          <SkeletonText lines={3} />
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
          <ErrorState
            message={error}
            action={
              <Button variant="secondary" onClick={() => window.location.reload()}>
                {t("common.retry") || "Retry"}
              </Button>
            }
          />
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

  function handleFormFieldsChange(nextFields: ApplicationFieldDef[]) {
    setAppFormConfig((prev) => (prev ? { ...prev, fields: nextFields } : prev));
    setFormSaveError(null);

    if (saveTimerRef.current) window.clearTimeout(saveTimerRef.current);
    if (savedIndicatorTimerRef.current) window.clearTimeout(savedIndicatorTimerRef.current);

    if (validateApplicationFields(nextFields).length > 0) {
      // Invalid draft: keep it visible locally, don't save yet.
      setSaveStatus("idle");
      return;
    }

    setSaveStatus("saving");
    saveTimerRef.current = window.setTimeout(async () => {
      try {
        const updated = await updateApplicationForm(id, nextFields);
        setAppFormConfig(updated);
        setSaveStatus("saved");
        savedIndicatorTimerRef.current = window.setTimeout(() => {
          setSaveStatus((current) => (current === "saved" ? "idle" : current));
        }, 2000);
      } catch (err) {
        setFormSaveError(getErrorMessage(err, t("applicationForm.saveFailed") || "Failed to save the application form. Please try again."));
        setSaveStatus("error");
      }
    }, SAVE_DEBOUNCE_MS);
  }

  async function handleCreateForm() {
    setCreatingForm(true);
    setFormSaveError(null);
    try {
      const created = await updateApplicationForm(id, buildDefaultApplicationFields());
      setAppFormConfig(created);
      notify.success(t("toast.jobCreated") || "Application form created");
    } catch (err) {
      setFormSaveError(getErrorMessage(err, t("applicationForm.createFailed") || "Failed to create the application form. Please try again."));
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
      notify.error(
        t("applicationForm.link.regenerateFailed") || "Failed to regenerate the application link",
        getErrorMessage(err),
      );
    } finally {
      setRegenerating(false);
    }
  }

  async function handleCopyLink() {
    const token = appFormConfig?.public_token;
    if (!token) return;
    const ok = await copyToClipboard(applicationUrl(token));
    if (ok) {
      notify.success(t("applicationForm.link.copiedToast") || "Link copied");
    } else {
      notify.error(t("applicationForm.link.copyFailedToast") || "Couldn't copy the link");
    }
  }

  const publicToken = appFormConfig?.public_token;
  const jobStatus = jobStatusFromToken(publicToken);
  const previewJobInfo = {
    company_name: job.company_name,
    position: job.position,
    description: job.description,
    required_skills: job.required_skills,
    required_experience: job.required_experience,
  };

  return (
    <div className="page">
      <PageMeta title={job.position} noindex />
      <PageHeader
        title={job.position}
        description={`${job.company_name} · ${t("jobs.created") || "Created"} ${formatDate(job.created_at)}`}
        action={
          <>
            <StatusBadge kind="job" value={jobStatus} />
            <Button variant="secondary" to={`/jobs/${job.id}/edit`} icon={<Edit3 size={15} />}>
              {t("common.edit") || "Edit"}
            </Button>
            <Button variant="secondary" onClick={() => navigate(`/applications?job=${job.id}`)} icon={<Users size={15} />}>
              {t("jobs.viewApplications") || "View Applications"}
            </Button>
            <Dropdown
              trigger={({ toggle, id: triggerId }) => (
                <button
                  type="button"
                  className="btn btn--secondary btn--icon"
                  id={triggerId}
                  onClick={toggle}
                  aria-label={t("jobs.moreActions") || "More actions"}
                >
                  <MoreHorizontal size={16} />
                </button>
              )}
            >
              {publicToken && (
                <>
                  <DropdownItem icon={<Copy size={14} />} onClick={handleCopyLink}>
                    {t("jobs.copyPublicLink") || "Copy Public Link"}
                  </DropdownItem>
                  <DropdownItem
                    icon={<ExternalLink size={14} />}
                    onClick={() => window.open(applicationUrl(publicToken), "_blank", "noreferrer")}
                  >
                    {t("jobs.openPublicLink") || "Open Public Link"}
                  </DropdownItem>
                  <DropdownSeparator />
                </>
              )}
              <DropdownItem icon={<Trash2 size={14} />} danger onClick={() => setConfirmDeleteJob(true)}>
                {t("common.delete") || "Delete"}
              </DropdownItem>
            </Dropdown>
          </>
        }
      />

      <Tabs
        items={[
          { id: "overview", label: t("jobs.tabs.overview") || "Overview" },
          { id: "form", label: t("jobs.tabs.applicationForm") || "Application Form" },
          { id: "applications", label: t("jobs.tabs.applications") || "Applications" },
        ]}
        activeId={activeTab}
        onChange={setActiveTab}
        ariaLabel={t("pages.jobDetails") || "Job details sections"}
        idPrefix="job-details"
      />

      <TabPanel id="overview" idPrefix="job-details" activeId={activeTab}>
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

          <Card title={t("jobs.candidateSummary") || "Candidate summary"}>
            <ul className="summary-list">
              <li><span>{t("candidates.total") || "Total candidates"}</span><strong>{analytics.total}</strong></li>
              <li className="success"><span>{t("statusMeta.hiring.strong_hire") || "Strong hires"}</span><strong>{analytics.strong_hires}</strong></li>
              <li className="info"><span>{t("statusMeta.hiring.hire") || "Hires"}</span><strong>{analytics.hires}</strong></li>
              <li className="warning"><span>{t("statusMeta.hiring.weak_hire") || "Weak hires"}</span><strong>{analytics.weak_hires}</strong></li>
              <li className="danger"><span>{t("statusMeta.hiring.do_not_hire") || "Do not hire"}</span><strong>{analytics.do_not_hires}</strong></li>
            </ul>
          </Card>
        </div>
      </TabPanel>

      <TabPanel id="form" idPrefix="job-details" activeId={activeTab}>
        {appFormLoading ? (
          <Card>
            <SkeletonText lines={4} />
          </Card>
        ) : appFormError ? (
          <Card>
            <ErrorState
              message={appFormError}
              action={
                <Button variant="secondary" onClick={loadApplicationForm}>
                  {t("common.retry") || "Retry"}
                </Button>
              }
            />
          </Card>
        ) : appFormConfig ? (
          <>
            <ApplicationLinkCard
              token={appFormConfig.public_token}
              jobTitle={job.position}
              onRegenerate={handleRegenerateLink}
              regenerating={regenerating}
            />
            <div className="form-save-status" aria-live="polite">
              {saveStatus === "saving" && (t("applicationForm.savingIndicator") || "Saving…")}
              {saveStatus === "saved" && (t("applicationForm.savedIndicator") || "Saved")}
            </div>
            <ApplicationFormBuilder
              fields={appFormConfig.fields}
              errors={formProblems}
              onFieldsChange={handleFormFieldsChange}
              previewJobInfo={previewJobInfo}
            />
          </>
        ) : (
          <Card>
            <EmptyState
              title={t("jobs.noFormYet") || "No application form yet"}
              message={t("jobs.noFormYetMessage") || "Start from the standard question set and customize each field right here."}
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
      </TabPanel>

      <TabPanel id="applications" idPrefix="job-details" activeId={activeTab}>
        <Card title={t("nav.applications") || "Applications for this job"} subtitle={t("jobs.applicationsSubtitle") || "AI-screened submissions."}>
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
                  hideOnMobile: true,
                  render: (application) => formatDate(application.submitted_at),
                },
              ]}
            />
          )}
        </Card>
      </TabPanel>

      <ConfirmDialog
        open={confirmDeleteJob}
        title={t("jobs.deleteConfirm") || "Delete this job?"}
        message={
          (t("jobs.deleteConfirmDetailedMessage") ||
            'This will permanently remove "{position}" at {company} and all its candidates.')
            .replace("{position}", job.position)
            .replace("{company}", job.company_name)
        }
        confirmLabel={t("jobs.deleteJobBtn") || "Delete"}
        cancelLabel={t("common.cancel") || "Cancel"}
        onConfirm={handleDeleteJob}
        onCancel={() => setConfirmDeleteJob(false)}
        disabled={deleting}
        loading={deleting}
      />
    </div>
  );
}
