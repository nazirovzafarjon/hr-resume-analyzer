import FormField from "./FormField";

type SelectOption = { value: string; label: string };

type SelectProps = {
  label: string;
  value: string;
  onChange: (value: string) => void;
  options: SelectOption[];
  required?: boolean;
  hint?: string;
  disabled?: boolean;
};

export default function Select({
  label,
  value,
  onChange,
  options,
  required,
  hint,
  disabled,
}: SelectProps) {
  return (
    <FormField label={label} required={required} hint={hint}>
      {(id) => (
        <select
          id={id}
          className="field-select"
          value={value}
          onChange={(event) => onChange(event.target.value)}
          disabled={disabled}
        >
          {options.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      )}
    </FormField>
  );
}