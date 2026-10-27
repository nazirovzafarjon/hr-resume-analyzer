import { useState, useEffect, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import AuthLayout from "../../components/auth/AuthLayout";
import PageMeta from "../../components/seo/PageMeta";
import AuthCard from "../../components/auth/AuthCard";
import AuthInput from "../../components/auth/AuthInput";
import PasswordInput from "../../components/auth/PasswordInput";
import AuthButton from "../../components/auth/AuthButton";
import AuthMessage from "../../components/auth/AuthMessage";
import GoogleAuthButton from "../../components/auth/GoogleAuthButton";
import PasswordRequirements from "../../components/auth/PasswordRequirements";
import Modal from "../../components/ui/Modal";
import { getPasswordError, isValidEmail } from "../../utils/validate";
import { register, resendVerification } from "../../services/authService";
import { useLanguage } from "../../contexts/LanguageContext";
import { ApiError, getErrorMessage } from "../../utils/apiError";

type FormErrors = {
  fullName?: string;
  email?: string;
  password?: string;
  confirmPassword?: string;
};

const RESEND_COOLDOWN_SECONDS = 60;

/** /register — initiate two-phase HR registration. */
export default function RegisterPage() {
  const { t } = useLanguage();
  const navigate = useNavigate();
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [errors, setErrors] = useState<FormErrors>({});
  const [serverError, setServerError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  // Two-phase verification modal state
  const [showVerifyModal, setShowVerifyModal] = useState(false);
  const [registeredEmail, setRegisteredEmail] = useState("");
  const [resending, setResending] = useState(false);
  const [resendCooldown, setResendCooldown] = useState(0);
  const [resendNotice, setResendNotice] = useState<string | null>(null);
  const [resendError, setResendError] = useState<string | null>(null);

  useEffect(() => {
    if (resendCooldown <= 0) return;
    const timer = window.setInterval(() => {
      setResendCooldown((prev) => (prev <= 1 ? 0 : prev - 1));
    }, 1000);
    return () => window.clearInterval(timer);
  }, [resendCooldown]);

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

      // Two-phase registration: zero tokens issued, open verification modal.
      // When the provider rejected the message the backend reports
      // verification_email_sent=false, so we must not claim it was sent.
      setRegisteredEmail(response.email || email.trim());
      setResendError(
        response.verification_email_sent === false
          ? response.email_delivery_error ||
              t("auth.emailDeliveryFailed") ||
              "We couldn't send the verification email. Use Resend Email to try again."
          : null,
      );
      setShowVerifyModal(true);
      setResendCooldown(RESEND_COOLDOWN_SECONDS);
    } catch (error) {
      setServerError(
        error instanceof ApiError && error.message
          ? error.message
          : getErrorMessage(error)
      );
    } finally {
      setLoading(false);
    }
  }

  async function handleResendFromModal() {
    if (!registeredEmail) return;
    setResending(true);
    setResendNotice(null);
    setResendError(null);
    try {
      await resendVerification(registeredEmail);
      setResendNotice(t("auth.codeSent") || "A fresh verification email has been sent.");
      setResendCooldown(RESEND_COOLDOWN_SECONDS);
    } catch (err) {
      setResendError(
        err instanceof ApiError && err.message ? err.message : getErrorMessage(err)
      );
    } finally {
      setResending(false);
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

        <GoogleAuthButton disabled={loading} />

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

      {/* Two-Phase Registration Verification Modal */}
      <Modal
        open={showVerifyModal}
        title={t("auth.verifyEmailTitle") || "Verify Your Email"}
        onClose={() => setShowVerifyModal(false)}
        size="md"
      >
        <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-md)" }}>
          {resendNotice && <AuthMessage type="success">{resendNotice}</AuthMessage>}
          {resendError && <AuthMessage type="error">{resendError}</AuthMessage>}

          <p style={{ color: "var(--color-text-secondary)", lineHeight: 1.6, margin: 0 }}>
            {resendError ? (
              <>
                We couldn't send a verification link to{" "}
                <strong>{registeredEmail}</strong> yet. Use Resend Email below to
                request it again.
              </>
            ) : (
              <>
                We've sent a verification link to{" "}
                <strong>{registeredEmail}</strong>. Please check your inbox and
                click the verification link to confirm that it's you and activate
                your account.
              </>
            )}
          </p>

          <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-sm)", marginTop: "var(--space-sm)" }}>
            <AuthButton
              type="button"
              variant="secondary"
              fullWidth
              loading={resending}
              disabled={resendCooldown > 0 || resending}
              onClick={handleResendFromModal}
            >
              {resendCooldown > 0
                ? `${t("auth.resendCode") || "Resend Email"} (${resendCooldown}s)`
                : t("auth.resendCode") || "Resend Email"}
            </AuthButton>

            <AuthButton
              type="button"
              variant="secondary"
              fullWidth
              onClick={() => {
                setShowVerifyModal(false);
                navigate("/verify-email", { state: { email: registeredEmail } });
              }}
            >
              {t("auth.manualVerifyOption") || "Enter 6-Digit Code Manually"}
            </AuthButton>

            <p style={{ textAlign: "center", margin: "var(--space-xs) 0 0", fontSize: "14px" }}>
              <Link className="auth-link" to="/login">
                {t("auth.backToSignIn") || "Back to sign in"}
              </Link>
            </p>
          </div>
        </div>
      </Modal>
    </AuthLayout>
  );
}
