import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import AuthLayout from "../../components/auth/AuthLayout";
import AuthCard from "../../components/auth/AuthCard";
import AuthInput from "../../components/auth/AuthInput";
import AuthButton from "../../components/auth/AuthButton";
import AuthMessage from "../../components/auth/AuthMessage";
import { isValidEmail } from "../../utils/validate";
import { forgotPassword } from "../../services/authService";
import { useLanguage } from "../../contexts/LanguageContext";
import { getErrorMessage } from "../../utils/apiError";

/** /forgot-password — request a password reset link. */
export default function ForgotPasswordPage() {
  const { t } = useLanguage();
  const [email, setEmail] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [serverError, setServerError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [sent, setSent] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (!email.trim()) {
      setError(t("auth.emailRequired") || "Email is required.");
      return;
    }
    if (!isValidEmail(email)) {
      setError(t("auth.invalidEmail") || "Enter a valid email address.");
      return;
    }

    setError(null);
    setLoading(true);
    setServerError(null);
    try {
      await forgotPassword({ email: email.trim() });
      setSent(true);
    } catch (error) {
      setServerError(getErrorMessage(error));
    } finally {
      setLoading(false);
    }
  }

  return (
    <AuthLayout>
      <AuthCard
        title={t("auth.forgotPassword") || "Forgot your password?"}
        subtitle={t("auth.forgotPasswordSubtitle") || "Enter your email and we'll help you reset your password."}
        footer={
          <>
            {t("auth.haveAccount") || "Remembered it?"}{" "}
            <Link className="auth-link" to="/login">
              {t("auth.login") || "Back to sign in"}
            </Link>
          </>
        }
      >
        {sent ? (
          <>
            <AuthMessage type="success">
              {t("auth.resetPasswordSuccess") || "If an account exists for the email you entered, you will receive a link to reset your password."}
            </AuthMessage>
            <p className="auth-forgot">
              <button
                type="button"
                className="auth-link auth-link--button"
                onClick={() => setSent(false)}
              >
                Use a different email
              </button>
            </p>
          </>
        ) : (
          <>
            {serverError && <AuthMessage type="error">{serverError}</AuthMessage>}

            <form className="auth-form" onSubmit={handleSubmit} noValidate>
              <AuthInput
                label={t("auth.email") || "Email"}
                type="email"
                value={email}
                onChange={(value) => {
                  setEmail(value);
                  if (error) setError(null);
                }}
                placeholder="you@company.com"
                autoComplete="email"
                error={error ?? undefined}
                disabled={loading}
              />
              <AuthButton loading={loading} fullWidth>
                {loading ? (t("common.loading") || "Sending…") : (t("auth.resetPassword") || "Send reset link")}
              </AuthButton>
            </form>
          </>
        )}
      </AuthCard>
    </AuthLayout>
  );
}
