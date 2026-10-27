import { useId, useState, type ChangeEvent } from "react";
import { Eye, EyeOff } from "lucide-react";

type PasswordInputProps = {
  label: string;
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  autoComplete?: string;
  error?: string;
  disabled?: boolean;
};

/** Password input with a show/hide visibility toggle (hidden by default). */
export default function PasswordInput({
  label,
  value,
  onChange,
  placeholder,
  autoComplete,
  error,
  disabled = false,
}: PasswordInputProps) {
  const id = useId();
  const errorId = `${id}-error`;
  const [visible, setVisible] = useState(false);

  function handleChange(event: ChangeEvent<HTMLInputElement>) {
    onChange(event.target.value);
  }

  return (
    <div className="field">
      <label className="field-label" htmlFor={id}>
        {label}
      </label>
      <div className="field-input-wrapper" style={{ position: "relative", width: "100%" }}>
        <input
          id={id}
          className={`field-input field-input--with-toggle${error ? " field-input--error" : ""}`}
          type={visible ? "text" : "password"}
          value={value}
          onChange={handleChange}
          placeholder={placeholder}
          autoComplete={autoComplete}
          disabled={disabled}
          aria-invalid={error ? true : undefined}
          aria-describedby={error ? errorId : undefined}
        />
        <button
          type="button"
          className="password-toggle"
          onClick={() => setVisible((current) => !current)}
          aria-label={visible ? "Hide password" : "Show password"}
          aria-pressed={visible}
          disabled={disabled}
          tabIndex={disabled ? -1 : 0}
        >
          {visible ? <EyeOff size={18} strokeWidth={1.8} aria-hidden="true" /> : <Eye size={18} strokeWidth={1.8} aria-hidden="true" />}
        </button>
      </div>
      {error && (
        <p className="field-error" id={errorId} role="alert">
          {error}
        </p>
      )}
    </div>
  );
}

