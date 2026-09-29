import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import AuthLayout from "../../components/auth/AuthLayout";
import PageMeta from "../../components/seo/PageMeta";
import AuthCard from "../../components/auth/AuthCard";
import AuthInput from "../../components/auth/AuthInput";
import PasswordInput from "../../components/auth/PasswordInput";
import AuthButton from "../../components/auth/AuthButton";
import AuthMessage from "../../components/auth/AuthMessage";
import PasswordRequirements from "../../components/auth/PasswordRequirements";
import { getPasswordError, isValidEmail } from "../../utils/validate";
import { register } from "../../services/authService";
import { useAuth } from "../../context/AuthContext";
import { useLanguage } from "../../contexts/LanguageContext";
import { getErrorMessage } from "../../utils/apiError";

type FormErrors = {
  fullName?: string;
  email?: string;
  password?: string;
  confirmPassword?: string;
};

/** /register — create an HR account, store the token and go to the dashboard. */
export default function RegisterPage() {
  const { t } = useLanguage();
  const navigate = useNavigate();
  const { signIn } = useAuth();
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [errors, setErrors] = useState<FormErrors>({});
  const [serverError, setServerError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  function validate(): FormErrors {
    const nextErrors: FormErrors = {};
    if (!fullName.trim()) {
      nextErrors.fullName = t("auth.nameRequired") || "Full name is required.";
    }
    if (!email.trim()) {
      nextErrors.email = t("auth.emailRequired") || "Email is required.";
    } else if (!isValidEmail(email)) {
      nextErrors.email = t("auth.invalidEmail") || "Enter a valid email address.";
    }
    const passwordError = getPasswordError(password);
    if (passwordError) {
      nextErrors.password = passwordError;
    }
    if (!confirmPassword) {
      nextErrors.confirmPassword = t("auth.confirmPasswordRequired") || "Please confirm your password.";
    } else if (confirmPassword !== password) {
      nextErrors.confirmPassword = t("auth.passwordMismatch") || "Passwords do not match.";
    }
    return nextErrors;
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const nextErrors = validate();
    setErrors(nextErrors);
    if (Object.keys(nextErrors).length > 0) return;

    setLoading(true);
    setServerError(null);
    try {
      const response = await register({
        full_name: fullName.trim(),
        email: email.trim(),
        password,
      });
      signIn(response);
      navigate("/dashboard");
    } catch (error) {
      setServerError(getErrorMessage(error));
    } finally {
      setLoading(false);
    }
  }

  return (
    <AuthLayout>
      <PageMeta title={t("auth.register")} />
      <AuthCard
        title={t("auth.register") || "Create your account"}
        subtitle={t("auth.registerSubtitle") || "Start managing your hiring workflow with Resume Analyzer."}
        footer={
          <>
            {t("auth.haveAccount") || "Already have an account?"}{" "}
            <Link className="auth-link" to="/login">
              {t("auth.login") || "Sign in"}
            </Link>
          </>
        }
      >
        {serverError && <AuthMessage type="error">{serverError}</AuthMessage>}

        <form className="auth-form" onSubmit={handleSubmit} noValidate>
          <AuthInput
            label={t("auth.name") || "Full name"}
            value={fullName}
            onChange={(value) => {
              setFullName(value);
              if (errors.fullName) {
                setErrors((prev) => ({ ...prev, fullName: undefined }));
              }
            }}
            placeholder={t("auth.namePlaceholder")}
            autoComplete="name"
            error={errors.fullName}
            disabled={loading}
          />
          <AuthInput
            label={t("auth.email") || "Email"}
            type="email"
            value={email}
            onChange={(value) => {
              setEmail(value);
              if (errors.email) {
                setErrors((prev) => ({ ...prev, email: undefined }));
              }
            }}
            placeholder="you@company.com"
            autoComplete="email"
            error={errors.email}
            disabled={loading}
          />
          <div>
            <PasswordInput
              label={t("auth.password") || "Password"}
              value={password}
              onChange={(value) => {
                setPassword(value);
                if (errors.password) {
                  setErrors((prev) => ({ ...prev, password: undefined }));
                }
              }}
              autoComplete="new-password"
              error={errors.password}
              disabled={loading}
            />
            <div style={{ marginTop: "var(--space-xs)" }}>
              <PasswordRequirements password={password} />
            </div>
          </div>
          <PasswordInput
            label={t("auth.confirmPassword") || "Confirm password"}
            value={confirmPassword}
            onChange={(value) => {
              setConfirmPassword(value);
              if (errors.confirmPassword) {
                setErrors((prev) => ({ ...prev, confirmPassword: undefined }));
              }
            }}
            autoComplete="new-password"
            error={errors.confirmPassword}
            disabled={loading}
          />
          <AuthButton loading={loading} fullWidth>
            {loading ? (t("common.loading") || "Creating account…") : (t("auth.register") || "Create account")}
          </AuthButton>
        </form>
      </AuthCard>
    </AuthLayout>
  );
}
