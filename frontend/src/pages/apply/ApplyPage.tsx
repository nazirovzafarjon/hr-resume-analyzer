/**
 * /apply/:token — public candidate application form.
 *
 * Loads the fixed field definitions from the backend, renders them
 * through the immutable PublicApplicationFormTemplate, validates
 * locally for fast feedback, then POSTs to the public submission
 * endpoint (no JWT — the token is the credential).
 */
import { useEffect, useRef, useState, useCallback } from "react";
import { useParams } from "react-router-dom";
import { getPublicApplication, submitPublicApplication } from "../../services/publicService";
import PublicApplicationFormTemplate from "../../components/application-form/PublicApplicationFormTemplate";
import ApplicationSuccess from "../../components/application-form/ApplicationSuccess";
import PageMeta from "../../components/seo/PageMeta";
import { useLanguage } from "../../contexts/LanguageContext";
import { validateApplicationValues } from "../../utils/applicationFields";
import { ApiError, getErrorMessage } from "../../utils/apiError";
import type { PublicApplication } from "../../types/applicationForm";
import type { ApplicationValues, ApplicationFieldErrors } from "../../types/applicationForm";

export default function ApplyPage() {
  const { t } = useLanguage();
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

  // Idiomatic unmount guard: a plain `let` at component scope does not reset
  // between React 18 StrictMode's dev-mode double mount/cleanup/mount, which
  // can leave `loading` stuck forever. A ref reset on every effect run does.
  const mountedRef = useRef(true);
  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  const loadApplication = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getPublicApplication(token);
      if (mountedRef.current) setApplication(data);
    } catch (err) {
      if (!mountedRef.current) return;
      if (err instanceof ApiError && err.status === 404) {
        setError("not_found");
      } else if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError(t("apply.loadFailed"));
      }
    } finally {
      if (mountedRef.current) setLoading(false);
    }
  }, [token, t]);

  useEffect(() => {
    loadApplication();
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
      if (mountedRef.current) setSubmitSuccess(true);
    } catch (err) {
      if (mountedRef.current) {
        // ApiError already carries the backend's friendly `detail` message.
        setSubmitError(getErrorMessage(err, t("apply.submitFailed")));
      }
    } finally {
      if (mountedRef.current) setSubmitting(false);
    }
  }

  if (loading) {
    return (
      <section className="apply-template" aria-label={t("apply.loadingAriaLabel")}>
        <PageMeta title={t("apply.defaultTitle")} />
        <p className="muted-note">{t("apply.loading")}</p>
      </section>
    );
  }

  if (error === "not_found") {
    return (
      <section className="apply-template" aria-label={t("apply.notFoundAriaLabel")}>
        <PageMeta title={t("apply.notFoundTitle")} />
        <div className="apply-success">
          <h1 className="apply-title">{t("apply.notFoundTitle")}</h1>
          <p className="apply-description">{t("apply.notFoundMessage")}</p>
        </div>
      </section>
    );
  }

  if (error) {
    return (
      <section className="apply-template" aria-label={t("apply.errorAriaLabel")}>
        <PageMeta title={t("apply.errorTitle")} />
        <div className="apply-success">
          <h1 className="apply-title">{t("apply.errorTitle")}</h1>
          <p className="apply-description">{error}</p>
        </div>
      </section>
    );
  }

  if (!application) return null;

  const position = application.job.position || t("apply.defaultTitle");
  const company = application.job.company_name;
  const pageTitle = company ? t("apply.pageTitleTemplate", { position, company }) : position;
  const metaDescription = company
    ? t("apply.metaDescriptionTemplate", { position, company })
    : undefined;

  if (submitSuccess) {
    return (
      <>
        <PageMeta title={pageTitle} noindex />
        <ApplicationSuccess position={application.job.position} company={application.job.company_name} />
      </>
    );
  }

  return (
    <section className="apply-template" aria-label={t("apply.formAriaLabel")}>
      <PageMeta
        title={pageTitle}
        description={metaDescription}
        og={{ title: pageTitle, description: metaDescription }}
      />
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
