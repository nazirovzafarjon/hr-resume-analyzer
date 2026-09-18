import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { fetchJob, updateJob } from "../../services/jobsService";
import PageHeader from "../../components/ui/PageHeader";
import Card from "../../components/ui/Card";
import Button from "../../components/ui/Button";
import EmptyState from "../../components/ui/EmptyState";
import JobForm from "../../components/jobs/JobForm";
import { ApiError } from "../../utils/apiError";
import type { JobInput } from "../../types/job";

/** /jobs/:id/edit — edit an existing job, reusing the shared job form. */
export default function JobEditPage() {
  const navigate = useNavigate();
  const params = useParams();
  const id = Number(params.id);
  const [job, setJob] = useState<JobInput | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;
    async function loadJob() {
      setLoading(true);
      setError(null);
      try {
        const data = await fetchJob(id);
        if (mounted) setJob(data);
      } catch (err) {
        if (mounted) {
          if (err instanceof ApiError && err.status === 404) {
            setError("not_found");
          } else if (err instanceof ApiError) {
            setError(err.message);
          } else {
            setError("Failed to load job. Please try again.");
          }
        }
      } finally {
        if (mounted) setLoading(false);
      }
    }
    loadJob();
    return () => {
      mounted = false;
    };
  }, [id]);

  if (loading) {
    return (
      <div className="page">
        <PageHeader title="Edit Job" description="Loading job details…" />
        <Card>
          <div className="loading-center">Loading…</div>
        </Card>
      </div>
    );
  }

  if (error === "not_found" || !job) {
    return (
      <div className="page">
        <PageHeader title="Job not found" description="This job may have been removed." />
        <Card>
          <EmptyState
            title="Job not found"
            message="The job you are trying to edit may have been deleted."
          />
        </Card>
      </div>
    );
  }

  if (error) {
    return (
      <div className="page">
        <PageHeader title="Error" description="Failed to load job." />
        <Card>
          <div className="error-center">
            <p>{error}</p>
            <Button onClick={() => window.location.reload()}>Retry</Button>
          </div>
        </Card>
      </div>
    );
  }

  return (
    <div className="page">
      <PageHeader
        title="Edit Job"
        description={`Update the vacancy details for ${job.company_name}.`}
      />
      <Card>
        <JobForm
          title={`Edit ${job.position}`}
          submitLabel="Save Changes"
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
              navigate(`/jobs/${id}`);
            } catch (err) {
              if (err instanceof ApiError) {
                alert(err.message);
              } else {
                alert("Failed to update job. Please try again.");
              }
            }
          }}
        />
      </Card>
    </div>
  );
}