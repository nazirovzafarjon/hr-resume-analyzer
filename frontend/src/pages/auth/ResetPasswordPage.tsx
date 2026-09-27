import { useCallback, useEffect, useState, type FormEvent } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import AuthLayout from "../../components/auth/AuthLayout";
import AuthCard from "../../components/auth/AuthCard";
import PasswordInput from "../../components/auth/PasswordInput";
import AuthButton from "../../components/auth/AuthButton";
import AuthMessage from "../../components/auth/AuthMessage";
import PasswordRequirements from "../../components/auth/PasswordRequirements";
import PageMeta from "../../components/seo/PageMeta";
import { useLanguage } from "../../contexts/LanguageContext";
import { getPasswordError } from "../../utils/validate";
import {
  resetPassword,
  skipPasswordReset,
  verifyResetToken,
} from "../../services/authService";
import { ApiError, getErrorMessage } from "../../utils/apiError";
import { useAuth } from "../../context/AuthContext";
import type { AuthResponse, ResetTokenInfo } from "../../types/auth";

type FormErrors = {
  newPassword?: string;
  confirmPassword?: string;
};

/** Whether the reset link on this page is usable, being checked, or dead. */
type LinkState = "checking" | "valid" | "invalid";

/** Which half of the page the user is looking at. */
type Mode = "choice" | "change";

/**
 * /reset-password — the landing page of an emailed reset link (?token=...).
 *
 * It offers the two ways out of a forgotten password:
 *
 * 1. **Skip** — keep the current password. `POST /auth/skip-reset` validates the
 *    link, mints a fresh access/refresh pair and the user lands on the
 *    dashboard. This is also the natural option for a Google-only account that
 *    would rather not carry a local password.
 * 2. **Change password** — `POST /auth/reset-password` hashes the new password,
 *    revokes every session issued before the change and returns a fresh pair,
 *    so the user is signed in as part of the reset instead of being bounced
 *    back to /login.
 *
 * On mount the token is verified once so the copy can match the account (for
 * example "add a password" rather than "change your password") and a dead link
 * is reported before the user wastes time filling in the form.
 */
export default function ResetPasswordPage() {
  const { t } = useLanguage();
  const [searchParams] = useSearchParams();
  const token = searchParams.get("token");
  const navigate = useNavigate();
  const { signIn } = useAuth();

  const [linkState, setLinkState] = useState<LinkState>(
    token ? "checking" : "invalid",
  );
  const [account, setAccount] = useState<ResetTokenInfo | null>(null);
  const [mode, setMode] = useState<Mode>("choice");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [errors, setErrors] = useState<FormErrors>({});
  const [serverError, setServerError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!token) return;
    let cancelled = false;
    verifyResetToken({ token })
      .then((info) => {
        if (cancelled) return;
        setAccount(info);
        setLinkState("valid");
      })
      .catch((error: unknown) => {
        if (cancelled) return;
        // A 400 is the backend rejecting the link itself. Anything else
        // (offline, 5xx) must not punish a perfectly good link, so the page
        // still renders and only shows a warning banner.
        if (error instanceof ApiError && error.status === 400) {
          setLinkState("invalid");
        } else {
          setServerError(getErrorMessage(error));
          setLinkState("valid");
        }
      });
    return () => {
      cancelled = true;
    };
  }, [token]);

  /** Store the issued pair and enter the app — shared by both options. */
  const complete = useCallback(
    (tokens: AuthResponse) => {
      signIn(tokens);
      navigate("/dashboard", { replace: true });
    },
    [navigate, signIn],
  );

  /** Map a rejected reset token to one consistent, actionable message. */
  const describeFailure = useCallback(
    (error: unknown) => {
      return error instanceof ApiError && error.status === 400
        ? t("auth.resetLinkInvalid")
        : getErrorMessage(error);
    },
    [t],
  );

  const handleSkip = useCallback(async () => {
    if (!token) return;
    setLoading(true);
    setServerError(null);
    try {
      complete(await skipPasswordReset({ token }));
    } catch (error) {
      setServerError(describeFailure(error));
      setLoading(false);
    }
  }, [complete, describeFailure, token]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    // The form is only rendered once the link has been verified (see the
    // guards below), but this keeps TypeScript happy and covers a cleared URL.
    if (!token) return;

    const nextErrors: FormErrors = {};
    const passwordError = getPasswordError(newPassword);
    if (passwordError) {
      nextErrors.newPassword = passwordError;
    }
    if (!confirmPassword) {
      nextErrors.confirmPassword = t("auth.confirmPasswordRequired");
    } else if (confirmPassword !== newPassword) {
      nextErrors.confirmPassword = t("auth.passwordMismatch");
    }
    setErrors(nextErrors);
    if (Object.keys(nextErrors).length > 0) return;

    setLoading(true);
    setServerError(null);
    try {
      complete(await resetPassword({ token, new_password: newPassword }));
    } catch (error) {
      // The backend reports invalid/expired tokens with a 400.
      setServerError(describeFailure(error));
      setLoading(false);
    }
  }

  const isGoogleOnlyAccount = Boolean(
    account && !account.has_password && account.is_google_account,
  );
  const title = isGoogleOnlyAccount
    ? t("auth.addPasswordTitle")
    : t("auth.createNewPasswordTitle");
  const subtitle = account
    ? t("auth.resetSubtitleWithEmail", { email: account.email })
    : t("auth.resetSubtitleGeneric");
  const footer = (
    <>
      {t("auth.rememberedIt")}{" "}
      <Link className="auth-link" to="/login">
        {t("auth.backToSignIn")}
      </Link>
    </>
  );

  // No token, or a token the backend refused → the link is broken, expired or
  // was already consumed by a password change.
  if (linkState === "invalid") {
    return (
      <AuthLayout>
        <PageMeta title={t("auth.resetPassword")} />
        <AuthCard title={title} subtitle={subtitle} footer={footer}>
          <AuthMessage type="error">{t("auth.resetLinkInvalid")}</AuthMessage>
          <p className="auth-forgot">
            <Link className="auth-link" to="/forgot-password">
              {t("auth.requestNewResetLink")}
            </Link>
          </p>
        </AuthCard>
      </AuthLayout>
    );
  }

  if (linkState === "checking") {
    return (
      <AuthLayout>
        <PageMeta title={t("auth.resetPassword")} />
        <AuthCard title={title} subtitle={subtitle} footer={footer}>
          <p className="auth-subtitle" role="status">
            {t("auth.checkingResetLink")}
          </p>
        </AuthCard>
      </AuthLayout>
    );
  }

  return (
    <AuthLayout>
      <PageMeta title={t("auth.resetPassword")} />
      <AuthCard title={title} subtitle={subtitle} footer={footer}>
        {serverError && <AuthMessage type="error">{serverError}</AuthMessage>}
        {isGoogleOnlyAccount && mode === "choice" && (
          <AuthMessage type="success">{t("auth.googleOnlyAccountNotice")}</AuthMessage>
        )}

        {mode === "change" ? (
          <form className="auth-form" onSubmit={handleSubmit} noValidate>
            <div className="field-group">
              <PasswordInput
                label={t("auth.newPassword")}
                value={newPassword}
                onChange={(value) => {
                  setNewPassword(value);
                  if (errors.newPassword) {
                    setErrors((prev) => ({ ...prev, newPassword: undefined }));
                  }
                }}
                autoComplete="new-password"
                error={errors.newPassword}
                disabled={loading}
              />
              <PasswordRequirements password={newPassword} />
            </div>
            <PasswordInput
              label={t("auth.confirmNewPassword")}
              value={confirmPassword}
              onChange={(value) => {
                setConfirmPassword(value);
                if (errors.confirmPassword) {
                  setErrors((prev) => ({
                    ...prev,
                    confirmPassword: undefined,
                  }));
                }
              }}
              autoComplete="new-password"
              error={errors.confirmPassword}
              disabled={loading}
            />
            <AuthButton loading={loading} fullWidth>
              {loading
                ? t("auth.updating")
                : isGoogleOnlyAccount
                  ? t("auth.setPasswordAndSignIn")
                  : t("auth.changePassword")}
            </AuthButton>
            <AuthButton
              type="button"
              variant="secondary"
              fullWidth
              disabled={loading}
              onClick={() => setMode("choice")}
            >
              {t("auth.back")}
            </AuthButton>
          </form>
        ) : (
          <div className="auth-choice">
            <p className="auth-choice-hint">{t("auth.notChangedYetHint")}</p>
            <AuthButton
              type="button"
              fullWidth
              disabled={loading}
              onClick={() => setMode("change")}
            >
              {isGoogleOnlyAccount ? t("auth.setAPassword") : t("auth.changePassword")}
            </AuthButton>
            <AuthButton
              type="button"
              variant="secondary"
              fullWidth
              loading={loading}
              onClick={handleSkip}
            >
              {loading ? t("auth.signingYouIn") : t("auth.skipKeepPassword")}
            </AuthButton>
          </div>
        )}
      </AuthCard>
    </AuthLayout>
  );
}
