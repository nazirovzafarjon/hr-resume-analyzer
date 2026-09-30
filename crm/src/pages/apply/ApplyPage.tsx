/**
 * /apply/:token — public candidate application form.
 *
 * Loads the fixed field definitions from the backend, renders them
 * through the immutable PublicApplicationFormTemplate inside the public
 * page shell, validates locally for fast feedback, then POSTs to the public
 * submission endpoint (no JWT — the token is the credential).
 *
 * Candidate Portal: a banner above the form offers an account (or shows who
 * is applying). A signed-in candidate's submission carries their candidate
 * token, so the application appears in their portal. The form template itself
 * is untouched.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { RotateCw } from "lucide-react";
import AuthLayout from "../../components/auth/AuthLayout";
import Button from "../../components/ui/Button";
import { Skeleton } from "../../components/ui/Skeleton";
import { getPublicApplication, submitPublicApplication } from "../../services/publicService";
import PublicApplicationFormTemplate from "../../components/application-form/PublicApplicationFormTemplate";
import ApplicationSuccess from "../../components/application-form/ApplicationSuccess";
import ApplyAccountBanner from "../../components/candidate/ApplyAccountBanner";
import { useCandidateAuth } from "../../context/CandidateAuthContext";
import PageMeta from "../../components/seo/PageMeta";
import { useLanguage } from "../../contexts/LanguageContext";
import { validateApplicationValues, validateResumeFile } from "../../utils/applicationFields";
import { ApiError } from "../../utils/apiError";
import type {
  ApplicationFieldDef,
  ApplicationFieldErrors,
  ApplicationValues,
  PublicApplication,
} from "../../types/applicationForm";

type LoadError = "not_found" | "failed";
type Outcome = "submitted" | "already_received";

const REQUIRED_LIST_PREFIX = "Please complete the required fields:";

/**
 * Attach a backend 422 message to the field(s) it is about.
 *
 * The backend reports one candidate-safe sentence that quotes the field label
 * (`"Email" must be a valid email address.`) or lists missing required labels.
 * Matching labels lets the message sit next to the right input; anything
 * unmatched stays a form-level message.
 */
function fieldErrorsFromServer(
  fields: ApplicationFieldDef[],
  detail: string,
  requiredMessage: (label: string) => string,
): ApplicationFieldErrors {
  const errors: ApplicationFieldErrors = {};
  if (detail.startsWith(REQUIRED_LIST_PREFIX)) {
    const listed = detail.slice(REQUIRED_LIST_PREFIX.length);
    for (const field of fields) {
      if (field.required && listed.includes(field.label)) {
        errors[field.id] = requiredMessage(field.label);
      }
    }
    return errors;
  }
  for (const field of fields) {
    if (detail.includes(`"${field.label}"`)) errors[field.id] = detail;
  }
  return errors;
}

/** Move keyboard focus to the first invalid field, in form order. */
function focusFirstInvalid(fields: ApplicationFieldDef[], errors: ApplicationFieldErrors) {
  const first = [...fields].sort((a, b) => a.order - b.order).find((field) => errors[field.id]);
  if (!first) return;
  const container = document.querySelector(`[data-field-id="${CSS.escape(first.id)}"]`);
  const control = container?.querySelector<HTMLElement>("input, select, textarea");
  control?.focus();
  container?.scrollIntoView({ block: "center", behavior: "smooth" });
}

function ApplySkeleton() {
  return (
    <div className="apply-template apply-skeleton" aria-hidden="true">
      <Skeleton width="30%" />
      <Skeleton variant="title" width="70%" height={32} />
      <Skeleton width="40%" />
      <div className="apply-form apply-form--card">
        {[0, 1, 2, 3].map((row) => (
          <div key={row} className="apply-field">
            <Skeleton width="35%" />
            <Skeleton variant="block" height={40} />
          </div>
        ))}
        <Skeleton variant="block" height={120} />
      </div>
    </div>
  );
}

export default function ApplyPage() {
  const { t } = useLanguage();
  const params = useParams();
  const token = params.token as string;
  const { isAuthenticated: candidateSignedIn, profile: candidateProfile } = useCandidateAuth();
  const [application, setApplication] = useState<PublicApplication | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<LoadError | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [outcome, setOutcome] = useState<Outcome | null>(null);
  const [values, setValues] = useState<ApplicationValues>({});
  const [files, setFiles] = useState<Record<string, File | null>>({});
  const [fieldErrors, setFieldErrors] = useState<ApplicationFieldErrors>({});
  // A ref, not state: two quick submits in one frame both see submitting=false.
  const inFlight = useRef(false);

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

  // Depends on the token only: translated messages are chosen at render time,
  // so switching language (or translations finishing loading) never refetches.
  const loadApplication = useCallback(async () => {
    setLoading(true);
    setLoadError(null);
    try {
      const data = await getPublicApplication(token);
      if (!mountedRef.current) return;
      const initial: ApplicationValues = {};
      for (const field of data.fields) {
        initial[field.id] = field.type === "multi_select" ? [] : "";
      }
      setValues(initial);
      setFiles({});
      setFieldErrors({});
      setApplication(data);
    } catch (err) {
      if (!mountedRef.current) return;
      setLoadError(err instanceof ApiError && err.status === 404 ? "not_found" : "failed");
    } finally {
      if (mountedRef.current) setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    loadApplication();
  }, [loadApplication]);

  // Signed-in candidates start with their name/email/phone filled in (only
  // empty fields; they can still edit everything before submitting).
  useEffect(() => {
    if (!application || !candidateProfile) return;
    setValues((prev) => {
      const next = { ...prev };
      for (const field of application.fields) {
        if (next[field.id]) continue;
        if (field.type === "email") next[field.id] = candidateProfile.email;
        else if (field.type === "phone" && candidateProfile.phone) next[field.id] = candidateProfile.phone;
        else if (["full_name", "name"].includes(field.key)) next[field.id] = candidateProfile.full_name;
      }
      return next;
    });
  }, [application, candidateProfile]);

  function clearFieldError(fieldId: string) {
    setFieldErrors((prev) => {
      if (!(fieldId in prev)) return prev;
      const next = { ...prev };
      delete next[fieldId];
      return next;
    });
  }

  function handleFieldChange(fieldId: string, value: ApplicationValues[string]) {
    setValues((prev) => ({ ...prev, [fieldId]: value }));
    clearFieldError(fieldId);
  }

  function handleFileChange(fieldId: string, file: File | null) {
    // Check a new file straight away; an invalid pick keeps the previous file.
    const problem = file ? validateResumeFile(file, t) : null;
    if (problem) {
      setFieldErrors((prev) => ({ ...prev, [fieldId]: problem }));
      return;
    }
    setFiles((prev) => ({ ...prev, [fieldId]: file }));
    clearFieldError(fieldId);
  }

  async function handleSubmit() {
    if (!application || inFlight.current) return;
    setSubmitError(null);

    const errors = validateApplicationValues(application.fields, values, files, t);
    setFieldErrors(errors);
    if (Object.keys(errors).length > 0) {
      setSubmitError(t("apply.checkFields"));
      focusFirstInvalid(application.fields, errors);
      return;
    }

    inFlight.current = true;
    setSubmitting(true);
    try {
      await submitPublicApplication(token, application.fields, values, files);
      if (mountedRef.current) setOutcome("submitted");
    } catch (err) {
      if (!mountedRef.current) return;
      if (!(err instanceof ApiError) || err.status >= 500) {
        setSubmitError(t("apply.serverUnavailable"));
      } else if (err.status === 0) {
        setSubmitError(t("apply.networkError"));
      } else if (err.status === 409) {
        setOutcome("already_received");
      } else if (err.status === 404) {
        setSubmitError(t("apply.notFoundMessage"));
      } else {
        const serverErrors =
          err.status === 422
            ? fieldErrorsFromServer(application.fields, err.message, (label) =>
                t("apply.errors.required", { label }),
              )
            : {};
        if (Object.keys(serverErrors).length > 0) {
          setFieldErrors(serverErrors);
          setSubmitError(t("apply.checkFields"));
          focusFirstInvalid(application.fields, serverErrors);
        } else {
          // Candidate-safe backend sentence (e.g. "Please reload the page").
          setSubmitError(err.message);
        }
      }
    } finally {
      inFlight.current = false;
      if (mountedRef.current) setSubmitting(false);
    }
  }

  let content;
  if (loading) {
    content = (
      <>
        <PageMeta title={t("apply.defaultTitle")} noindex />
        <p className="sr-only" role="status">
          {t("apply.loadingAriaLabel")}
        </p>
        <ApplySkeleton />
      </>
    );
  } else if (loadError || !application) {
    const notFound = loadError === "not_found";
    const title = notFound ? t("apply.notFoundTitle") : t("apply.errorTitle");
    content = (
      <section className="apply-template apply-state" aria-labelledby="apply-state-title">
        <PageMeta title={title} noindex />
        <h1 id="apply-state-title" className="apply-title">
          {title}
        </h1>
        <p className="apply-description">
          {notFound ? t("apply.notFoundMessage") : t("apply.loadFailed")}
        </p>
        {!notFound && (
          <Button variant="secondary" icon={<RotateCw size={16} />} onClick={loadApplication}>
            {t("apply.retry")}
          </Button>
        )}
      </section>
    );
  } else {
    const { job } = application;
    const position = job.position || t("apply.defaultTitle");
    const pageTitle = job.company_name
      ? t("apply.pageTitleTemplate", { position, company: job.company_name })
      : position;
    const metaDescription = job.company_name
      ? t("apply.metaDescriptionTemplate", { position, company: job.company_name })
      : undefined;

    content = outcome ? (
      <>
        <PageMeta title={pageTitle} noindex />
        <ApplicationSuccess
          position={job.position}
          company={job.company_name}
          alreadyReceived={outcome === "already_received"}
        />
        <div className="apply-account-banner" role="note">
          <p>{candidateSignedIn ? t("portal.apply.trackMessage") : t("portal.apply.guestAfter")}</p>
          <div className="apply-account-actions">
            <Link className="btn btn--primary btn--sm" to={candidateSignedIn ? "/candidate/applications" : "/candidate/register"}>
              {candidateSignedIn ? t("portal.apply.track") : t("portal.auth.createAccount")}
            </Link>
          </div>
        </div>
      </>
    ) : (
      <>
        <PageMeta
          title={pageTitle}
          description={metaDescription}
          og={{ title: pageTitle, description: metaDescription }}
        />
        <ApplyAccountBanner returnTo={`/apply/${token}`} />
        <PublicApplicationFormTemplate
          job={job}
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
      </>
    );
  }

  return (
    <AuthLayout>
      <div className="apply-page">{content}</div>
    </AuthLayout>
  );
}
