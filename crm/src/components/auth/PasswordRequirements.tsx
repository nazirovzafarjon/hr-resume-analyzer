import { Check } from "lucide-react";
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
    <div className="requirements-container">
      <ul className="requirements" aria-label="Password requirements">
        {requirements.map((requirement) => (
          <li
            key={requirement.label}
            className={requirement.met ? "is-met" : undefined}
          >
            <span className="requirement-icon" aria-hidden="true">
              {requirement.met ? (
                <Check size={10} strokeWidth={3.2} />
              ) : (
                <span style={{ width: "4px", height: "4px", borderRadius: "50%", backgroundColor: "currentColor" }} />
              )}
            </span>
            {requirement.label}
          </li>
        ))}
      </ul>
    </div>
  );
}

