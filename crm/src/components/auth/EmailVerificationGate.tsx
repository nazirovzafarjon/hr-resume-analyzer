import { useEffect, useRef, useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import AuthLayout from "./AuthLayout";
import AuthCard from "./AuthCard";
import AuthInput from "./AuthInput";
import AuthButton from "./AuthButton";
import AuthMessage from "./AuthMessage";
import PageMeta from "../seo/PageMeta";
import { useLanguage } from "../../contexts/LanguageContext";
import { getErrorMessage } from "../../utils/apiError";

/** Seconds the resend button stays disabled after a successful send. */
const RESEND_COOLDOWN_SECONDS = 60;

type Props = {
  /** The token from the emailed verification link, or null on the pending page. */
  token: string | null;
  /** Email to prefill (from the registration response / session), if known. */
  defaultEmail?: string;
  /** Where "back to sign in" points (HR vs Candidate login). */
  loginPath: string;
  /**
   * Consume the link token and store the resulting session. Returns the path to
   * continue to on success; throws ApiError(400) for an invalid link.
   */
  onVerify: (token: string) => Promise<string>;
  /** Send a fresh verification email. */
  onResend: (email: string) => Promise<void>;
  /** Re-check the account; returns a path when verified, else null. */
  onCheckStatus: () => Promise<string | null>;
};

type Phase = "verifying" | "pending" | "success" | "error";

/**
 * Shared "verify your email" screen for HR and Candidate registration.
 *
 * With a `token` (the emailed link) it verifies and continues automatically;
 * without one it shows the manual gate: the required notice, a resend button
 * and a "check status" action. The backend is the real authority — this only
 * presents the flow.
 */
export default function EmailVerificationGate({
  token,
  defaultEmail = "",
  loginPath,
  onVerify,
  onResend,
  onCheckStatus,
}: Props) {
  const { t } = useLanguage();
  const navigate = useNavigate();
  const [phase, setPhase] = useState<Phase>(token ? "verifying" : "pending");
  const [email, setEmail] = useState(defaultEmail);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [checking, setChecking] = useState(false);
  const [cooldown, setCooldown] = useState(0);
  const startedRef = useRef(false);

  // Verify the link exactly once (StrictMode double-invokes effects).
  useEffect(() => {
    if (!token || startedRef.current) return;
    startedRef.current = true;
    let active = true;
    onVerify(token)
      .then((path) => {
        if (!active) return;
        setPhase("success");
        navigate(path, { replace: true });
      })
      .catch((err) => {
        if (!active) return;
        setError(getErrorMessage(err));
        setPhase("error");
      });
    return () => {
      active = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  // Count down the resend cooldown.
  useEffect(() => {
    if (cooldown <= 0) return;
    const id = window.setInterval(() => {
      setCooldown((value) => (value <= 1 ? 0 : value - 1));
    }, 1000);
    return () => window.clearInterval(id);
  }, [cooldown]);

  async function handleResend(event?: FormEvent<HTMLFormElement>) {
    event?.preventDefault();
    setError(null);
    setNotice(null);
    if (!email.trim()) {
      setError(t("auth.emailRequired"));
      return;
    }
    setBusy(true);
    try {
      await onResend(email.trim());
      setNotice(t("auth.resendSent"));
      setCooldown(RESEND_COOLDOWN_SECONDS);
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  async function handleCheck() {
    setError(null);
    setNotice(null);
    setChecking(true);
    try {
      const path = await onCheckStatus();
      if (path) {
        navigate(path, { replace: true });
      } else {
        setNotice(t("auth.stillUnverified"));
      }
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setChecking(false);
    }
  }

  const title =
    phase === "error"
      ? t("auth.verifyEmailTitle")
      : phase === "success"
        ? t("auth.emailVerifiedContinuing")
        : t("auth.verifyEmailTitle");

  return (
    <AuthLayout>
      <PageMeta title={t("auth.verifyEmailTitle")} />
      <AuthCard title={title} subtitle={t("auth.verifyEmailInstructions")}>
        {/* The exact notice the requirement asks for, always visible. */}
        <div className="alert alert--error" role="alert">
          <span>{t("auth.verifyEmailBanner")}</span>
        </div>

        {phase === "verifying" && (
          <p className="auth-subtitle" role="status">
            {t("auth.verifyingEmail")}
          </p>
        )}

        {phase === "success" && (
          <AuthMessage type="success">{t("auth.emailVerifiedContinuing")}</AuthMessage>
        )}

        {(phase === "pending" || phase === "error") && (
          <>
            {error && <AuthMessage type="error">{error}</AuthMessage>}
            {notice && <AuthMessage type="success">{notice}</AuthMessage>}
            {phase === "error" && (
              <p className="auth-subtitle">{t("auth.verificationLinkInvalid")}</p>
            )}

            <form className="auth-form" onSubmit={handleResend} noValidate>
              <AuthInput
                label={t("auth.email")}
                type="email"
                value={email}
                onChange={setEmail}
                placeholder="you@example.com"
                autoComplete="email"
                disabled={busy || cooldown > 0}
              />
              <AuthButton loading={busy} fullWidth disabled={cooldown > 0}>
                {cooldown > 0
                  ? `${t("auth.resendVerification")} (${cooldown})`
                  : t("auth.resendVerification")}
              </AuthButton>
            </form>

            <div className="auth-divider" role="separator">
              {t("auth.orSignInWithEmail")}
            </div>

            <AuthButton
              type="button"
              variant="secondary"
              fullWidth
              loading={checking}
              onClick={handleCheck}
            >
              {t("auth.checkVerificationStatus")}
            </AuthButton>

            <p className="auth-forgot">
              <Link className="auth-link" to={loginPath}>
                {t("auth.backToSignIn")}
              </Link>
            </p>
          </>
        )}
      </AuthCard>
    </AuthLayout>
  );
}
