import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { fetchJob, updateJob } from "../../services/jobsService";
import PageHeader from "../../components/ui/PageHeader";
import PageMeta from "../../components/seo/PageMeta";
import Card from "../../components/ui/Card";
import Button from "../../components/ui/Button";
import EmptyState from "../../components/ui/EmptyState";
import ErrorState from "../../components/ui/ErrorState";
import { Skeleton, SkeletonText } from "../../components/ui/Skeleton";
import JobForm from "../../components/jobs/JobForm";
import { useLanguage } from "../../contexts/LanguageContext";
import { useNotify } from "../../contexts/ToastContext";
import { ApiError, getErrorMessage } from "../../utils/apiError";
import type { JobInput } from "../../types/job";

/** /jobs/:id/edit — edit an existing job, reusing the shared job form. */
export default function JobEditPage() {
  const { t } = useLanguage();
  const notify = useNotify();
  const navigate = useNavigate();
  const params = useParams();
  const id = Number(params.id);
  const [job, setJob] = useState<JobInput | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  function loadJob() {
    let cancelled = false;
    setLoading(true);
    setError(null);
    fetchJob(id)
      .then((data) => !cancelled && setJob(data))
      .catch((err) => {
        if (cancelled) return;
        if (err instanceof ApiError && err.status === 404) {
          setError("not_found");
        } else {
          setError(getErrorMessage(err, t("jobs.error")));
        }
      })
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }

  useEffect(() => loadJob(), [id]); // eslint-disable-line react-hooks/exhaustive-deps

  if (loading) {
    return (
      <div className="page">
        <PageHeader title={t("jobs.editJob")} description={t("jobs.loading")} />
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
        <PageHeader title={t("jobs.jobNotFound")} description={t("jobs.jobNotFoundDescription")} />
        <Card>
          <EmptyState
            title={t("jobs.jobNotFound")}
            message={t("jobs.jobNotFoundEditMessage")}
          />
        </Card>
      </div>
    );
  }

  if (error) {
    return (
      <div className="page">
        <PageHeader title={t("common.error")} description={t("jobs.error")} />
        <Card>
          <ErrorState
            message={error}
            action={
              <Button variant="secondary" onClick={loadJob}>
                {t("common.retry")}
              </Button>
            }
          />
        </Card>
      </div>
    );
  }

  return (
    <div className="page">
      <PageMeta title={t("jobs.editPageTitle", { position: job.position })} noindex />
      <PageHeader
        title={t("jobs.editJob")}
        description={t("jobs.editPageDescription", { company: job.company_name })}
      />
      <Card>
        <JobForm
          key={job.id}
          submitLabel={t("jobs.saveChanges")}
          initial={{
            company_name: job.company_name,
            position: job.position,
            required_experience: job.required_experience,
            required_skills: job.required_skills,
            description: job.description,
          }}
          onSubmit={async (input) => {
            try {
              await updateJob(id, input);
              notify.success(t("toast.jobUpdated"));
              navigate(`/jobs/${id}`);
            } catch (err) {
              notify.error(t("jobs.updateFailed"), getErrorMessage(err));
            }
          }}
        />
      </Card>
    </div>
  );
}
