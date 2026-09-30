/**
 * Renders ONE application field on the public form, driven entirely by the
 * field-type registry. This component is part of the FIXED public template:
 * its layout, spacing and behaviour never depend on AI output — only on the
 * structured field definition.
 */

import { useId } from "react";
import { CircleAlert } from "lucide-react";
import ResumeUpload from "./ResumeUpload";
import { useLanguage } from "../../contexts/LanguageContext";
import { MAX_TEXT_VALUE_LENGTH } from "../../utils/applicationFields";
import type {
  ApplicationFieldDef,
  ApplicationFieldValue,
} from "../../types/applicationForm";

/**
 * Browser autofill hint from the field's type or machine key. Keys come from
 * the label ("Full name" -> "full_name"), so the common identity questions
 * get the right suggestions without any change to the stored configuration.
 */
function autoCompleteFor(field: ApplicationFieldDef): string | undefined {
  if (field.type === "email") return "email";
  if (field.type === "phone") return "tel";
  if (field.type === "url") return "url";
  if (field.type === "text" && /(^|_)(full_)?name$/.test(field.key)) return "name";
  return undefined;
}

type ApplicationFieldProps = {
  field: ApplicationFieldDef;
  value: ApplicationFieldValue;
  /** The selected File for `file` fields (kept outside `values`). */
  file?: File | null;
  error?: string;
  disabled?: boolean;
  onChange: (value: ApplicationFieldValue) => void;
  onFileChange?: (file: File | null) => void;
};

export default function ApplicationField({
  field,
  value,
  file = null,
  error,
  disabled,
  onChange,
  onFileChange,
}: ApplicationFieldProps) {
  const { t } = useLanguage();
  const uid = useId();
  const inputId = `${uid}-${field.id}`;
  const errorId = `${uid}-${field.id}-error`;
  const describedBy =
    [field.description ? `${inputId}-desc` : "", error ? errorId : ""]
      .filter(Boolean)
      .join(" ") || undefined;

  const showError = Boolean(error);
  const inputClass = `apply-input${showError ? " apply-input--error" : ""}`;

  const requiredStars = field.required ? 1 : 0;

  const labelNode = (
    <label className="apply-field-label" htmlFor={inputId}>
      {field.label}
      {requiredStars === 1 && (
        <span className="apply-required" aria-hidden="true">
          {" "}
          *
        </span>
      )}
      {requiredStars === 1 && <span className="sr-only"> ({t("apply.requiredSr")})</span>}
    </label>
  );

  const descriptionNode = field.description ? (
    <p id={`${inputId}-desc`} className="apply-field-description">
      {field.description}
    </p>
  ) : null;

  // Not a live region: after a submit the form announces one summary and
  // focuses the first invalid field, which reads this via aria-describedby.
  const errorNode = showError ? (
    <p id={errorId} className="apply-field-error">
      <CircleAlert size={14} aria-hidden="true" />
      <span>{error}</span>
    </p>
  ) : null;

  switch (field.type) {
    case "textarea":
      return (
        <div className="apply-field" data-field-id={field.id}>
          {labelNode}
          {descriptionNode}
          <textarea
            id={inputId}
            className={`${inputClass} apply-input--textarea`}
            value={typeof value === "string" ? value : ""}
            onChange={(e) => onChange(e.target.value)}
            rows={5}
            maxLength={MAX_TEXT_VALUE_LENGTH}
            disabled={disabled}
            required={field.required}
            aria-invalid={showError || undefined}
            aria-describedby={describedBy}
          />
          <div className="apply-field-footer">
            {errorNode}
            <span className="apply-char-count">
              {t("apply.charCount", {
                count: typeof value === "string" ? value.length : 0,
                max: MAX_TEXT_VALUE_LENGTH,
              })}
            </span>
          </div>
        </div>
      );

    case "select":
      return (
        <div className="apply-field" data-field-id={field.id}>
          {labelNode}
          {descriptionNode}
          <select
            id={inputId}
            className={inputClass}
            value={typeof value === "string" ? value : ""}
            onChange={(e) => onChange(e.target.value)}
            disabled={disabled}
            required={field.required}
            aria-invalid={showError || undefined}
            aria-describedby={describedBy}
          >
            <option value="">{t("apply.selectPlaceholder")}</option>
            {field.options.map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </select>
          {errorNode}
        </div>
      );

    case "multi_select":
      return (
        <fieldset
          className="apply-field apply-fieldset"
          disabled={disabled}
          data-field-id={field.id}
          aria-invalid={showError || undefined}
          aria-describedby={describedBy}
        >
          <legend className="apply-field-label">
            {field.label}
            {requiredStars === 1 && (
              <span className="apply-required" aria-hidden="true">
                {" "}
                *
              </span>
            )}
            {requiredStars === 1 && <span className="sr-only"> ({t("apply.requiredSr")})</span>}
          </legend>
          {descriptionNode}
          <div className="apply-checkbox-group">
            {field.options.map((option) => {
              const selected = Array.isArray(value) && value.includes(option);
              return (
                <label key={option} className="apply-checkbox-option">
                  <input
                    type="checkbox"
                    checked={selected}
                    onChange={(e) => {
                      const current = Array.isArray(value) ? value.map(String) : [];
                      onChange(
                        e.target.checked
                          ? [...current, option]
                          : current.filter((o) => o !== option)
                      );
                    }}
                    name={inputId}
                    value={option}
                  />
                  <span>{option}</span>
                </label>
              );
            })}
          </div>
          {errorNode}
        </fieldset>
      );

    case "checkbox":
      return (
        <div className="apply-field apply-field--checkbox" data-field-id={field.id}>
          <label className="apply-checkbox-option">
            <input
              id={inputId}
              type="checkbox"
              checked={value === true}
              onChange={(e) => onChange(e.target.checked)}
              disabled={disabled}
              aria-invalid={showError || undefined}
              aria-describedby={describedBy}
            />
            <span>
              {field.label}
              {requiredStars === 1 && (
                <span className="apply-required" aria-hidden="true">
                  {" "}
                  *
                </span>
              )}
              {requiredStars === 1 && <span className="sr-only"> ({t("apply.requiredSr")})</span>}
            </span>
          </label>
          {descriptionNode}
          {errorNode}
        </div>
      );

    case "file":
      return (
        <div className="apply-field" data-field-id={field.id}>
          {labelNode}
          {descriptionNode}
          <ResumeUpload
            inputId={inputId}
            file={file}
            required={field.required}
            disabled={disabled}
            invalid={showError}
            describedBy={describedBy}
            onFileChange={onFileChange}
          />
          {errorNode}
        </div>
      );

    // text / email / phone / number / date / url
    default: {
      const inputType =
        field.type === "email"
          ? "email"
          : field.type === "phone"
            ? "tel"
            : field.type === "number"
              ? "number"
              : field.type === "date"
                ? "date"
                : field.type === "url"
                  ? "url"
                  : "text";
      return (
        <div className="apply-field" data-field-id={field.id}>
          {labelNode}
          {descriptionNode}
          <input
            id={inputId}
            type={inputType}
            autoComplete={autoCompleteFor(field)}
            maxLength={field.type === "number" ? undefined : MAX_TEXT_VALUE_LENGTH}
            className={inputClass}
            value={typeof value === "string" ? value : ""}
            onChange={(e) => onChange(e.target.value)}
            disabled={disabled}
            required={field.required}
            inputMode={field.type === "number" ? "decimal" : undefined}
            aria-invalid={showError || undefined}
            aria-describedby={describedBy}
          />
          {errorNode}
        </div>
      );
    }
  }
}
