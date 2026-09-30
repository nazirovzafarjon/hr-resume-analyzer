type Option<T extends string> = { value: T; label: string };

type SegmentedControlProps<T extends string> = {
  value: T;
  onChange: (value: T) => void;
  options: Option<T>[];
  disabled?: boolean;
  ariaLabel: string;
};

/** Small segmented toggle (period range, groupBy dimension, bar-chart mode, ...). */
export default function SegmentedControl<T extends string>({
  value,
  onChange,
  options,
  disabled = false,
  ariaLabel,
}: SegmentedControlProps<T>) {
  return (
    <div className="segmented" role="group" aria-label={ariaLabel}>
      {options.map((option) => (
        <button
          key={option.value}
          type="button"
          className={`segmented-button${value === option.value ? " is-active" : ""}`}
          onClick={() => onChange(option.value)}
          disabled={disabled}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}
