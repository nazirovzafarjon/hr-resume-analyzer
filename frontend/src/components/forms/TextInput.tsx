import FormField from "./FormField";

type TextInputProps = {
  label: string;
  value: string;
  onChange: (value: string) => void;
  required?: boolean;
  hint?: string;
  placeholder?: string;
  error?: string;
  autoComplete?: string;
  disabled?: boolean;
  type?: "text" | "email" | "password" | "number" | "tel" | "url";
};

export default function TextInput({
  label,
  value,
  onChange,
  required,
  hint,
  placeholder,
  error,
  autoComplete,
  disabled,
  type = "text",
}: TextInputProps) {
  return (
    <FormField label={label} required={required} hint={hint} error={error}>
      {(id, errorId) => (
        <input
          id={id}
          type={type}
          className={`field-input${error ? " field-input--error" : ""}`}
          value={value}
          onChange={(event) => onChange(event.target.value)}
          placeholder={placeholder}
          autoComplete={autoComplete}
          disabled={disabled}
          aria-invalid={error ? true : undefined}
          aria-describedby={error ? errorId : undefined}
        />
      )}
    </FormField>
  );
}