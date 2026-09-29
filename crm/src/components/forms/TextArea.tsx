import FormField from "./FormField";

type TextAreaProps = {
  label: string;
  value: string;
  onChange: (value: string) => void;
  required?: boolean;
  hint?: string;
  placeholder?: string;
  error?: string;
  rows?: number;
  disabled?: boolean;
};

export default function TextArea({
  label,
  value,
  onChange,
  required,
  hint,
  placeholder,
  error,
  rows = 4,
  disabled,
}: TextAreaProps) {
  return (
    <FormField label={label} required={required} hint={hint} error={error}>
      {(id, errorId) => (
        <textarea
          id={id}
          className={`field-input field-input--textarea${error ? " field-input--error" : ""}`}
          value={value}
          onChange={(event) => onChange(event.target.value)}
          placeholder={placeholder}
          rows={rows}
          disabled={disabled}
          aria-invalid={error ? true : undefined}
          aria-describedby={error ? errorId : undefined}
        />
      )}
    </FormField>
  );
}