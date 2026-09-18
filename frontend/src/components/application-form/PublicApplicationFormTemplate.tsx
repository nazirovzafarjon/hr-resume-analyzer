/**
 * PublicApplicationFormTemplate — THE fixed internal template that renders
 * the candidate-facing application form.
 *
 * Architectural rule: this component owns the entire public form's layout,
 * spacing, typography, validation-message placement, navigation and visual
 * hierarchy. AI (or any other source) may only supply the structured field
 * definitions rendered inside it — never markup, styles or structure.
 *
 * It is deliberately the ONLY renderer for the candidate form so the Review
 * preview and the public /apply page can never drift apart. Changing the AI
 * model cannot change this UI; only the field data can change.
 */

import ApplicationField from "./ApplicationField";
import Button from "../ui/Button";
import { sortedFields } from "../../utils/applicationFields";
import type {
  ApplicationFieldDef,
  ApplicationFieldErrors,
  ApplicationValues,
  PublicJobInfo,
} from "../../types/applicationForm";

type PublicApplicationFormTemplateProps = {
  job: PublicJobInfo;
  fields: ApplicationFieldDef[];
  values: ApplicationValues;
  /** Selected files keyed by field id. */
  files?: Record<string, File | null>;
  fieldErrors?: ApplicationFieldErrors;
  formError?: string | null;
  submitting?: boolean;
  /** "preview" renders the identical form with submitting disabled. */
  mode?: "public" | "preview";
  onFieldChange: (fieldId: string, value: ApplicationValues[string]) => void;
  onFileChange?: (fieldId: string, file: File | null) => void;
  onSubmit?: () => void;
};

export default function PublicApplicationFormTemplate({
  job,
  fields,
  values,
  files,
  fieldErrors = {},
  formError = null,
  submitting = false,
  mode = "public",
  onFieldChange,
  onFileChange,
  onSubmit,
}: PublicApplicationFormTemplateProps) {
  const ordered = sortedFields(fields);
  const isPreview = mode === "preview";

  function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (!isPreview) onSubmit?.();
  }

  return (
    <section className="apply-template" aria-label="Application form">
      <header className="apply-header">
        {job.company_name && (
          <p className="apply-company">{job.company_name}</p>
        )}
        <h1 className="apply-title">{job.position || "Application"}</h1>
        {job.description && <p className="apply-description">{job.description}</p>}
        {(job.required_skills || job.required_experience) && (
          <div className="apply-meta">
            {job.required_experience && (
              <span className="chip">{job.required_experience}</span>
            )}
            {job.required_skills
              .split(",")
              .map((s) => s.trim())
              .filter(Boolean)
              .slice(0, 8)
              .map((skill) => (
                <span key={skill} className="chip chip--info">
                  {skill}
                </span>
              ))}
          </div>
        )}
      </header>

      <form className="apply-form" onSubmit={handleSubmit} noValidate>
        <h2 className="apply-form-title">
          {isPreview ? "Application (preview)" : "Application"}
        </h2>
        <p className="apply-form-subtitle">
          Fields marked with <span className="apply-required">*</span> are required.
        </p>

        <div className="apply-fields">
          {ordered.map((field) => (
            <ApplicationField
              key={field.id}
              field={field}
              value={values[field.id] ?? null}
              file={files?.[field.id] ?? null}
              error={fieldErrors[field.id]}
              disabled={submitting || isPreview}
              onChange={(value) => onFieldChange(field.id, value)}
              onFileChange={onFileChange ? (file) => onFileChange(field.id, file) : undefined}
            />
          ))}
        </div>

        {formError && (
          <div className="apply-form-error" role="alert">
            <strong>We couldn't submit your application.</strong>
            <p>{formError}</p>
            <p className="muted-note">Please check your information and try again.</p>
          </div>
        )}

        <div className="apply-submit">
          {isPreview ? (
            <Button type="button" disabled>
              Submit Application
            </Button>
          ) : (
            <Button type="submit" loading={submitting} disabled={submitting}>
              {submitting ? "Submitting…" : "Submit Application"}
            </Button>
          )}
          {isPreview && (
            <p className="muted-note">
              Live preview — candidates will see exactly this form.
            </p>
          )}
        </div>
      </form>
    </section>
  );
}
