import { useState, type FormEvent } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import AuthLayout from "../../components/auth/AuthLayout";
import PageMeta from "../../components/seo/PageMeta";
import AuthCard from "../../components/auth/AuthCard";
import AuthInput from "../../components/auth/AuthInput";
import PasswordInput from "../../components/auth/PasswordInput";
import AuthButton from "../../components/auth/AuthButton";
import AuthMessage from "../../components/auth/AuthMessage";
import GoogleAuthButton from "../../components/auth/GoogleAuthButton";
import { isValidEmail } from "../../utils/validate";
import { login } from "../../services/authService";
import { useAuth } from "../../context/AuthContext";
import { useLanguage } from "../../contexts/LanguageContext";
import { ApiError, getErrorMessage } from "../../utils/apiError";

type FormErrors = {
  email?: string;
  password?: string;
};

/** /login — email + password sign-in. */
export default function LoginPage() {
  const { t } = useLanguage();
  const navigate = useNavigate();
  const { completeSignIn } = useAuth();
  const [searchParams] = useSearchParams();
  const sessionExpired = searchParams.get("expired") === "1";

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [errors, setErrors] = useState<FormErrors>({});
  const [serverError, setServerError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  function validate(): FormErrors {
    const nextErrors: FormErrors = {};
    if (!email.trim()) {
      nextErrors.email = t("auth.emailRequired") || "Email is required.";
    } else if (!isValidEmail(email)) {
      nextErrors.email = t("auth.invalidEmail") || "Enter a valid email address.";
    }
    if (!password) {
      nextErrors.password = t("auth.passwordRequired") || "Password is required.";
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
      const response = await login({ email: email.trim(), password });
      const path = completeSignIn(response);
      // Unverified accounts must confirm their email before the panel works.
      if (!("requires_role_selection" in response) && response.is_email_verified === false) {
        navigate("/verify-email", { state: { email: email.trim() } });
        return;
      }
      // Straight into the workspace, or to the workspace choice.
      navigate(path);
    } catch (error) {
      if (
        error instanceof ApiError &&
        error.status === 403 &&
        error.code === "EMAIL_VERIFICATION_REQUIRED"
      ) {
        // The account exists but the email is not confirmed yet.
        navigate("/verify-email", { state: { email: email.trim() } });
        return;
      }
      if (error instanceof ApiError && error.status === 401) {
        setServerError(t("auth.invalidCredentials") || "Invalid email or password.");
      } else {
        setServerError(getErrorMessage(error));
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <AuthLayout>
      <PageMeta title={t("auth.login")} />
      <AuthCard
        title={t("auth.welcomeBack") || "Welcome back"}
        subtitle={t("auth.loginSubtitle") || "Sign in to continue managing your hiring workflow."}
        footer={
          <>
            {t("auth.noAccount") || "Don't have an account?"}{" "}
            <Link className="auth-link" to="/register">
              {t("auth.register") || "Create one"}
            </Link>
          </>
        }
      >
        {sessionExpired && (
          <AuthMessage type="error">
            {t("auth.sessionExpired") || "Your session has expired. Please log in again."}
          </AuthMessage>
        )}
        {serverError && <AuthMessage type="error">{serverError}</AuthMessage>}

        <GoogleAuthButton disabled={loading} />

        <form className="auth-form" onSubmit={handleSubmit} noValidate>
          <AuthInput
            label={t("auth.email") || "Email"}
            type="email"
            value={email}
            onChange={(value) => {
              setEmail(value);
              if (errors.email) setErrors((prev) => ({ ...prev, email: undefined }));
            }}
            placeholder="you@company.com"
            autoComplete="email"
            error={errors.email}
            disabled={loading}
          />
          <PasswordInput
            label={t("auth.password") || "Password"}
            value={password}
            onChange={(value) => {
              setPassword(value);
              if (errors.password) {
                setErrors((prev) => ({ ...prev, password: undefined }));
              }
            }}
            autoComplete="current-password"
            error={errors.password}
            disabled={loading}
          />
          <AuthButton loading={loading} fullWidth>
            {loading ? (t("common.loading") || "Signing in…") : (t("auth.login") || "Sign in")}
          </AuthButton>
        </form>

        <p className="auth-forgot">
          <Link className="auth-link" to="/forgot-password">
            {t("auth.forgotPassword") || "Forgot your password?"}
          </Link>
        </p>
      </AuthCard>
    </AuthLayout>
  );
}
