import { PASSWORD_MAX_LENGTH } from "../../utils/validate";

type PasswordRequirementsProps = {
  password: string;
};

/**
 * Live checklist shown under the password fields on Register and
 * Reset Password. It mirrors the backend's actual constraints
 * (required value, bcrypt 72-byte limit) — stricter rules must be
 * added together with backend validation, not invented here.
 */
export default function PasswordRequirements({ password }: PasswordRequirementsProps) {
  const requirements = [
    { label: "Cannot be empty", met: password.length > 0 },
    {
      label: `At most ${PASSWORD_MAX_LENGTH} characters`,
      met: password.length <= PASSWORD_MAX_LENGTH,
    },
  ];

  return (
    <ul className="requirements" aria-label="Password requirements">
      {requirements.map((requirement) => (
        <li
          key={requirement.label}
          className={requirement.met ? "is-met" : undefined}
        >
          <CheckIcon />
          {requirement.label}
        </li>
      ))}
    </ul>
  );
}

function CheckIcon() {
  return (
    <svg
      width="12"
      height="12"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="3"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <polyline points="20 6 9 17 4 12" />
    </svg>
  );
}
