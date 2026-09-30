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

import { useId, useState } from "react";
import { Building, CircleAlert, ShieldCheck } from "lucide-react";
import ApplicationField from "./ApplicationField";
import Button from "../ui/Button";
import { useLanguage } from "../../contexts/LanguageContext";
import { sortedFields } from "../../utils/applicationFields";
import type {
  ApplicationFieldDef,
  ApplicationFieldErrors,
  ApplicationValues,
  PublicJobInfo,
} from "../../types/applicationForm";

/** Descriptions longer than this start collapsed behind "Show more". */
const DESCRIPTION_PREVIEW_CHARS = 420;

type PublicApplicationFormTemplateProps = {
  job: PublicJobInfo;
  fields: ApplicationFieldDef[];
  values: ApplicationValues;
  /** Selected files keyed by field id. */
  files?: Record<string, File | null>;
  fieldErrors?: ApplicationFieldErrors;
  /** Form-level message (validation summary or submission failure). */
  formError?: string | null;
  submitting?: boolean;
  /** "preview" renders the identical form with submitting disabled. */
  mode?: "public" | "preview";
  onFieldChange: (fieldId: string, value: ApplicationValues[string]) => void;
  onFileChange?: (fieldId: string, file: File | null) => void;
  onSubmit?: () => void;
};

function JobDescription({ text }: { text: string }) {
  const { t } = useLanguage();
  const id = useId();
  const long = text.length > DESCRIPTION_PREVIEW_CHARS;
  const [expanded, setExpanded] = useState(false);
  return (
    <div className="apply-about">
      <h2 className="apply-about-title">{t("apply.aboutRole")}</h2>
      <p
        id={id}
        className={`apply-description${long && !expanded ? " apply-description--clamped" : ""}`}
      >
        {text}
      </p>
      {long && (
        <button
          type="button"
          className="apply-description-toggle"
          aria-expanded={expanded}
          aria-controls={id}
          onClick={() => setExpanded((current) => !current)}
        >
          {expanded ? t("apply.showLess") : t("apply.showMore")}
        </button>
      )}
    </div>
  );
}

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
  const { t } = useLanguage();
  const titleId = useId();
  const ordered = sortedFields(fields);
  const isPreview = mode === "preview";
  const skills = job.required_skills
    .split(",")
    .map((skill) => skill.trim())
    .filter(Boolean)
    .slice(0, 8);

  function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (!isPreview) onSubmit?.();
  }

  return (
    <article className="apply-template" aria-labelledby={titleId}>
      <header className="apply-header">
        <p className="apply-eyebrow">{t("apply.eyebrow")}</p>
        <h1 id={titleId} className="apply-title">
          {job.position || t("apply.defaultTitle")}
        </h1>
        {job.company_name && (
          <p className="apply-company">
            <Building size={16} aria-hidden="true" />
            {job.company_name}
          </p>
        )}
        {(job.required_experience || skills.length > 0) && (
          <ul className="apply-meta">
            {job.required_experience && <li className="chip">{job.required_experience}</li>}
            {skills.map((skill) => (
              <li key={skill} className="chip chip--info">
                {skill}
              </li>
            ))}
          </ul>
        )}
        {job.description && <JobDescription text={job.description} />}
      </header>

      <form
        className={`apply-form${isPreview ? "" : " apply-form--card"}`}
        onSubmit={handleSubmit}
        noValidate
        aria-busy={submitting || undefined}
      >
        <div className="apply-form-head">
          <h2 className="apply-form-title">
            {isPreview ? t("apply.applicationPreview") : t("apply.formHeading")}
          </h2>
          <p className="apply-form-subtitle">
            {t("apply.requiredFieldsPrefix")} <span className="apply-required">*</span>{" "}
            {t("apply.requiredFieldsSuffix")}
          </p>
        </div>

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
            <CircleAlert size={18} aria-hidden="true" />
            <p>{formError}</p>
          </div>
        )}

        <div className="apply-submit">
          {isPreview ? (
            <Button type="button" size="lg" disabled>
              {t("apply.submit")}
            </Button>
          ) : (
            <Button type="submit" size="lg" loading={submitting} disabled={submitting}>
              {submitting ? t("apply.submitting") : t("apply.submit")}
            </Button>
          )}
          {isPreview ? (
            <p className="muted-note">{t("applicationForm.previewNote")}</p>
          ) : (
            <p className="apply-privacy">
              <ShieldCheck size={16} aria-hidden="true" />
              <span>{t("apply.privacyNotice")}</span>
            </p>
          )}
        </div>
      </form>
    </article>
  );
}
