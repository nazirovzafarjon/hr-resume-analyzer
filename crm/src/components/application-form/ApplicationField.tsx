/**
 * Renders ONE application field on the public form, driven entirely by the
 * field-type registry. This component is part of the FIXED public template:
 * its layout, spacing and behaviour never depend on AI output — only on the
 * structured field definition.
 */

import { useId } from "react";
import type {
  ApplicationFieldDef,
  ApplicationFieldValue,
} from "../../types/applicationForm";

const RESUME_ACCEPT = ".pdf,.doc,.docx,.txt";

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
      {requiredStars === 1 && <span className="sr-only"> (required)</span>}
    </label>
  );

  const descriptionNode = field.description ? (
    <p id={`${inputId}-desc`} className="apply-field-description">
      {field.description}
    </p>
  ) : null;

  const errorNode = showError ? (
    <p id={errorId} className="field-error" role="alert">
      {error}
    </p>
  ) : null;

  switch (field.type) {
    case "textarea":
      return (
        <div className="apply-field">
          {labelNode}
          {descriptionNode}
          <textarea
            id={inputId}
            className={`${inputClass} apply-input--textarea`}
            value={typeof value === "string" ? value : ""}
            onChange={(e) => onChange(e.target.value)}
            rows={4}
            disabled={disabled}
            required={field.required}
            aria-invalid={showError || undefined}
            aria-describedby={describedBy}
          />
          {errorNode}
        </div>
      );

    case "select":
      return (
        <div className="apply-field">
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
            <option value="">Select an option…</option>
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
        <fieldset className="apply-field apply-fieldset" disabled={disabled}>
          <legend className="apply-field-label">
            {field.label}
            {requiredStars === 1 && (
              <span className="apply-required" aria-hidden="true">
                {" "}
                *
              </span>
            )}
            {requiredStars === 1 && <span className="sr-only"> (required)</span>}
          </legend>
          {descriptionNode}
          <div className="apply-checkbox-group" aria-describedby={describedBy}>
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
        <div className="apply-field apply-field--checkbox">
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
              {requiredStars === 1 && <span className="sr-only"> (required)</span>}
            </span>
          </label>
          {descriptionNode}
          {errorNode}
        </div>
      );

    case "file":
      return (
        <div className="apply-field">
          {labelNode}
          {descriptionNode}
          <input
            id={inputId}
            type="file"
            className="apply-file-input"
            accept={RESUME_ACCEPT}
            onChange={(e) => onFileChange?.(e.target.files?.[0] ?? null)}
            disabled={disabled}
            required={field.required && !file}
            aria-invalid={showError || undefined}
            aria-describedby={describedBy}
          />
          {file && (
            <p className="apply-file-selected">
              Selected: {file.name} ({(file.size / 1024).toFixed(1)} KB)
              <button
                type="button"
                className="row-action"
                onClick={() => {
                  onFileChange?.(null);
                  const input = document.getElementById(inputId) as HTMLInputElement | null;
                  if (input) input.value = "";
                }}
                disabled={disabled}
              >
                Remove
              </button>
            </p>
          )}
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
        <div className="apply-field">
          {labelNode}
          {descriptionNode}
          <input
            id={inputId}
            type={inputType}
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
