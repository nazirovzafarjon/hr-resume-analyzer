import { useEffect, useState, type FormEvent } from "react";
import { Link, useLocation, useNavigate, useSearchParams } from "react-router-dom";
import AuthLayout from "../../components/auth/AuthLayout";
import AuthCard from "../../components/auth/AuthCard";
import AuthInput from "../../components/auth/AuthInput";
import AuthButton from "../../components/auth/AuthButton";
import AuthMessage from "../../components/auth/AuthMessage";
import OtpInput from "../../components/auth/OtpInput";
import PageMeta from "../../components/seo/PageMeta";
import { useAuth } from "../../context/AuthContext";
import { useLanguage } from "../../contexts/LanguageContext";
import { resendVerification, verifyEmail } from "../../services/authService";
import { ApiError, getErrorMessage } from "../../utils/apiError";
import { isValidEmail } from "../../utils/validate";

/** Seconds the resend button stays disabled after a successful send. */
const RESEND_COOLDOWN_SECONDS = 60;
const CODE_LENGTH = 6;

/**
 * /verify-email — the HR email-verification screen.
 *
 * Supports two flows:
 * 1. Verification link token (?token=...): Renders explicit confirmation view ("It's me").
 * 2. 6-digit OTP code input: User enters the emailed code to complete account verification.
 */
export default function VerifyEmailPage() {
  const { t } = useLanguage();
  const navigate = useNavigate();
  const location = useLocation();
  const [searchParams] = useSearchParams();
  const token = searchParams.get("token");
  const { completeSignIn } = useAuth();

  const navState = location.state as {
    email?: string;
    emailDeliveryFailed?: boolean;
    emailDeliveryError?: string | null;
  } | null;

  const initialEmail = navState?.email ?? "";
  const [email, setEmail] = useState(initialEmail);
  const [code, setCode] = useState("");
  const [error, setError] = useState<string | null>(
    navState?.emailDeliveryFailed
      ? navState.emailDeliveryError ||
          "Could not deliver verification email. Please check your email configuration or click 'Resend Code' to try again."
      : null,
  );
  const [notice, setNotice] = useState<string | null>(null);
  const [verifying, setVerifying] = useState(false);
  const [resending, setResending] = useState(false);
  const [cooldown, setCooldown] = useState(0);

  useEffect(() => {
    if (cooldown <= 0) return;
    const id = window.setInterval(() => {
      setCooldown((value) => (value <= 1 ? 0 : value - 1));
    }, 1000);
    return () => window.clearInterval(id);
  }, [cooldown]);

  async function handleConfirmLink() {
    if (!token) return;
    setError(null);
    setVerifying(true);
    try {
      const result = await verifyEmail({ token });
      navigate(completeSignIn(result), { replace: true });
    } catch (err) {
      setError(
        err instanceof ApiError && err.status === 400
          ? err.message || "This verification link is invalid or has expired."
          : getErrorMessage(err),
      );
    } finally {
      setVerifying(false);
    }
  }

  async function handleSubmitOtp(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setNotice(null);
    if (!isValidEmail(email)) {
      setError(t("auth.invalidEmail") || "Enter a valid email address.");
      return;
    }
    if (code.length !== CODE_LENGTH) {
      setError(t("auth.invalidCode") || "Please enter the 6-digit code.");
      return;
    }
    setVerifying(true);
    try {
      const result = await verifyEmail(email.trim(), code);
      navigate(completeSignIn(result), { replace: true });
    } catch (err) {
      setError(
        err instanceof ApiError && err.status === 400
          ? err.message || t("auth.invalidCode") || "Invalid or expired verification code."
          : getErrorMessage(err),
      );
    } finally {
      setVerifying(false);
    }
  }

  async function handleResend() {
    setError(null);
    setNotice(null);
    if (!isValidEmail(email)) {
      setError(t("auth.invalidEmail") || "Enter a valid email address.");
      return;
    }
    setResending(true);
    try {
      await resendVerification(email.trim());
      setNotice(t("auth.codeSent") || "A fresh verification code and link has been sent.");
      setCooldown(RESEND_COOLDOWN_SECONDS);
    } catch (err) {
      setError(
        err instanceof ApiError && err.message
          ? err.message
          : getErrorMessage(err),
      );
    } finally {
      setResending(false);
    }
  }

  // Token-based link verification UI
  if (token) {
    return (
      <AuthLayout>
        <PageMeta title={t("auth.confirmEmailTitle") || "Confirm Your Email"} />
        <AuthCard
          title={t("auth.confirmEmailTitle") || "Confirm Your Email"}
          subtitle={
            t("auth.confirmEmailSubtitle") ||
            "Click the button below to confirm that it's you and complete registration."
          }
        >
          {error && <AuthMessage type="error">{error}</AuthMessage>}

          <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-md)", marginTop: "var(--space-md)" }}>
            <p style={{ color: "var(--color-text-secondary)", lineHeight: 1.6, margin: 0 }}>
              To protect your security against automated link scanners, click the confirmation button below to complete creating your account.
            </p>

            <AuthButton
              loading={verifying}
              fullWidth
              onClick={handleConfirmLink}
            >
              {verifying
                ? (t("common.loading") || "Verifying…")
                : (t("auth.confirmItsMeButton") || "It's me — Complete Registration")}
            </AuthButton>

            <p className="auth-forgot" style={{ textAlign: "center", marginTop: "var(--space-sm)" }}>
              <Link className="auth-link" to="/login">
                {t("auth.backToSignIn") || "Back to sign in"}
              </Link>
            </p>
          </div>
        </AuthCard>
      </AuthLayout>
    );
  }

  // OTP code verification UI
  return (
    <AuthLayout>
      <PageMeta title={t("auth.otpTitle")} />
      <AuthCard title={t("auth.otpTitle")} subtitle={t("auth.otpSubtitle")}>
        {error && <AuthMessage type="error">{error}</AuthMessage>}
        {notice && <AuthMessage type="success">{notice}</AuthMessage>}

        <form className="auth-form" onSubmit={handleSubmitOtp} noValidate>
          <AuthInput
            label={t("auth.email")}
            type="email"
            value={email}
            onChange={setEmail}
            placeholder="you@company.com"
            autoComplete="email"
            disabled={verifying || Boolean(initialEmail)}
          />
          <OtpInput
            value={code}
            onChange={setCode}
            length={CODE_LENGTH}
            disabled={verifying}
            autoFocus
            label={t("auth.otpTitle")}
          />
          <div style={{ marginTop: "var(--space-xs)" }}>
            <AuthButton loading={verifying} fullWidth disabled={code.length !== CODE_LENGTH}>
              {t("auth.verifyEmailButton")}
            </AuthButton>
          </div>
        </form>

        <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-sm)", marginTop: "var(--space-md)" }}>
          <AuthButton
            type="button"
            variant="secondary"
            fullWidth
            loading={resending}
            disabled={cooldown > 0 || resending}
            onClick={handleResend}
          >
            {cooldown > 0
              ? `${t("auth.resendCode")} (${cooldown})`
              : t("auth.resendCode")}
          </AuthButton>
        </div>

        <p className="auth-forgot">
          <Link className="auth-link" to="/login">
            {t("auth.backToSignIn")}
          </Link>
        </p>
      </AuthCard>
    </AuthLayout>
  );
}
