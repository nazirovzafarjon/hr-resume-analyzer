import { useId, type ChangeEvent } from "react";

type AuthInputProps = {
  label: string;
  value: string;
  onChange: (value: string) => void;
  type?: "text" | "email";
  placeholder?: string;
  autoComplete?: string;
  error?: string;
  disabled?: boolean;
};

/** Text/email input with label, validation error, focus and disabled states. */
export default function AuthInput({
  label,
  value,
  onChange,
  type = "text",
  placeholder,
  autoComplete,
  error,
  disabled = false,
}: AuthInputProps) {
  const id = useId();
  const errorId = `${id}-error`;

  function handleChange(event: ChangeEvent<HTMLInputElement>) {
    onChange(event.target.value);
  }

  return (
    <div className="field">
      <label className="field-label" htmlFor={id}>
        {label}
      </label>
      <input
        id={id}
        className={`field-input${error ? " field-input--error" : ""}`}
        type={type}
        value={value}
        onChange={handleChange}
        placeholder={placeholder}
        autoComplete={autoComplete}
        disabled={disabled}
        aria-invalid={error ? true : undefined}
        aria-describedby={error ? errorId : undefined}
      />
      {error && (
        <p className="field-error" id={errorId} role="alert">
          {error}
        </p>
      )}
    </div>
  );
}
