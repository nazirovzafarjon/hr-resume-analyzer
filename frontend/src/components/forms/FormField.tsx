import { useId, type ReactNode } from "react";

type FormFieldProps = {
  label: string;
  required?: boolean;
  hint?: string;
  error?: string;
  children: (id: string, errorId: string) => ReactNode;
};

/**
 * Shared labelled field wrapper: renders the label (with the required marker),
 * an optional hint, the control itself and an inline error. The control is
 * passed the generated ids so it can associate label/error correctly.
 */
export default function FormField({
  label,
  required = false,
  hint,
  error,
  children,
}: FormFieldProps) {
  const id = useId();
  const errorId = `${id}-error`;

  return (
    <div className="field">
      <label className="field-label" htmlFor={id}>
        {label}
        {required && <span aria-hidden="true"> *</span>}
      </label>
      {children(id, errorId)}
      {hint && !error && <p className="field-hint">{hint}</p>}
      {error && (
        <p className="field-error" id={errorId} role="alert">
          {error}
        </p>
      )}
    </div>
  );
}