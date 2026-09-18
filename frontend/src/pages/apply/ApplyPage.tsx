/**
 * /apply/:token — public candidate application form.
 *
 * Loads the fixed field definitions from the backend, renders them
 * through the immutable PublicApplicationFormTemplate, validates
 * locally for fast feedback, then POSTs to the public submission
 * endpoint (no JWT — the token is the credential).
 */
import { useEffect, useState, useCallback } from "react";
import { useParams } from "react-router-dom";
import { getPublicApplication, submitPublicApplication } from "../../services/publicService";
import PublicApplicationFormTemplate from "../../components/application-form/PublicApplicationFormTemplate";
import ApplicationSuccess from "../../components/application-form/ApplicationSuccess";
import { validateApplicationValues } from "../../utils/applicationFields";
import { ApiError, getErrorMessage } from "../../utils/apiError";
import type { PublicApplication } from "../../types/applicationForm";
import type { ApplicationValues, ApplicationFieldErrors } from "../../types/applicationForm";

export default function ApplyPage() {
  const params = useParams();
  const token = params.token as string;
  const [application, setApplication] = useState<PublicApplication | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [submitSuccess, setSubmitSuccess] = useState(false);
  const [values, setValues] = useState<ApplicationValues>({});
  const [files, setFiles] = useState<Record<string, File | null>>({});
  const [fieldErrors, setFieldErrors] = useState<ApplicationFieldErrors>({});
  let mounted = true;

  const loadApplication = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getPublicApplication(token);
      setApplication(data);
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) {
        setError("not_found");
      } else if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError("Failed to load the application form. Please try again.");
      }
    } finally {
      if (mounted) setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    loadApplication();
    return () => { mounted = false; };
  }, [loadApplication]);

  useEffect(() => {
    if (application) {
      const initial: ApplicationValues = {};
      for (const field of application.fields) {
        if (field.type === "multi_select") {
          initial[field.id] = [];
        } else {
          initial[field.id] = "";
        }
      }
      setValues(initial);
      setFiles({});
      setFieldErrors({});
    }
  }, [application]);

  function handleFieldChange(fieldId: string, value: ApplicationValues[string]) {
    setValues((prev) => ({ ...prev, [fieldId]: value }));
    setFieldErrors((prev) => {
      const next = { ...prev };
      delete next[fieldId];
      return next;
    });
  }

  function handleFileChange(fieldId: string, file: File | null) {
    setFiles((prev) => ({ ...prev, [fieldId]: file }));
    setFieldErrors((prev) => {
      const next = { ...prev };
      delete next[fieldId];
      return next;
    });
  }

  async function handleSubmit() {
    setSubmitError(null);
    if (!application) return;
    const errors = validateApplicationValues(application.fields, values, files);
    setFieldErrors(errors);
    if (Object.keys(errors).length > 0) return;
    setSubmitting(true);
    try {
      await submitPublicApplication(token, application.fields, values, files);
      setSubmitSuccess(true);
    } catch (err) {
      if (mounted) {
        // ApiError already carries the backend's friendly `detail` message.
        setSubmitError(getErrorMessage(err, "Submission failed. Please try again."));
      }
    } finally {
      if (mounted) setSubmitting(false);
    }
  }

  if (loading) {
    return (
      <section className="apply-template" aria-label="Loading application">
        <p className="muted-note">Loading the application form...</p>
      </section>
    );
  }

  if (error === "not_found") {
    return (
      <section className="apply-template" aria-label="Application not found">
        <div className="apply-success">
          <h1 className="apply-title">Application not found</h1>
          <p className="apply-description">The application link you followed is invalid or has expired.</p>
        </div>
      </section>
    );
  }

  if (error) {
    return (
      <section className="apply-template" aria-label="Error loading application">
        <div className="apply-success">
          <h1 className="apply-title">Something went wrong</h1>
          <p className="apply-description">{error}</p>
        </div>
      </section>
    );
  }

  if (!application) return null;
  if (submitSuccess) {
    return <ApplicationSuccess position={application.job.position} company={application.job.company_name} />;
  }

  return (
    <section className="apply-template" aria-label="Application form">
      <header className="apply-header">
        {application.job.company_name && <p className="apply-company">{application.job.company_name}</p>}
        <h1 className="apply-title">{application.job.position || "Application"}</h1>
        {application.job.description && <p className="apply-description">{application.job.description}</p>}
        {(application.job.required_skills || application.job.required_experience) && (
          <div className="apply-meta">
            {application.job.required_experience && <span className="chip">{application.job.required_experience}</span>}
            {application.job.required_skills.split(",").map((s) => s.trim()).filter(Boolean).slice(0, 8).map((skill) => (
              <span key={skill} className="chip chip--info">{skill}</span>
            ))}
          </div>
        )}
      </header>
      <PublicApplicationFormTemplate
        job={application.job}
        fields={application.fields}
        values={values}
        files={files}
        fieldErrors={fieldErrors}
        formError={submitError}
        submitting={submitting}
        mode="public"
        onFieldChange={handleFieldChange}
        onFileChange={handleFileChange}
        onSubmit={handleSubmit}
      />
    </section>
  );
}
