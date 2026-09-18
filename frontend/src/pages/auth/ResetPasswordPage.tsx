import { useCallback, useEffect, useState, type FormEvent } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import AuthLayout from "../../components/auth/AuthLayout";
import AuthCard from "../../components/auth/AuthCard";
import PasswordInput from "../../components/auth/PasswordInput";
import AuthButton from "../../components/auth/AuthButton";
import AuthMessage from "../../components/auth/AuthMessage";
import PasswordRequirements from "../../components/auth/PasswordRequirements";
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
  const describeFailure = useCallback((error: unknown) => {
    return error instanceof ApiError && error.status === 400
      ? "This reset link is invalid or has expired. Please request a new one."
      : getErrorMessage(error);
  }, []);

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
      nextErrors.confirmPassword = "Please confirm your new password.";
    } else if (confirmPassword !== newPassword) {
      nextErrors.confirmPassword = "Passwords do not match.";
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
    ? "Add a password to your account"
    : "Create a new password";
  const subtitle = account
    ? `Resetting access for ${account.email}. Choose a new password, or keep your current one.`
    : "Choose a new password for your Resume Analyzer account, or keep your current one.";
  const footer = (
    <>
      Remembered it?{" "}
      <Link className="auth-link" to="/login">
        Back to sign in
      </Link>
    </>
  );

  // No token, or a token the backend refused → the link is broken, expired or
  // was already consumed by a password change.
  if (linkState === "invalid") {
    return (
      <AuthLayout>
        <AuthCard title={title} subtitle={subtitle} footer={footer}>
          <AuthMessage type="error">
            This password reset link is invalid or has expired. Please request
            a new one.
          </AuthMessage>
          <p className="auth-forgot">
            <Link className="auth-link" to="/forgot-password">
              Request a new reset link
            </Link>
          </p>
        </AuthCard>
      </AuthLayout>
    );
  }

  if (linkState === "checking") {
    return (
      <AuthLayout>
        <AuthCard title={title} subtitle={subtitle} footer={footer}>
          <p className="auth-subtitle" role="status">
            Checking your reset link…
          </p>
        </AuthCard>
      </AuthLayout>
    );
  }

  return (
    <AuthLayout>
      <AuthCard title={title} subtitle={subtitle} footer={footer}>
        {serverError && <AuthMessage type="error">{serverError}</AuthMessage>}
        {isGoogleOnlyAccount && mode === "choice" && (
          <AuthMessage type="success">
            This account signs in with Google. Setting a password adds a second
            way to sign in — your Google button keeps working either way, and
            you can skip this entirely.
          </AuthMessage>
        )}

        {mode === "change" ? (
          <form className="auth-form" onSubmit={handleSubmit} noValidate>
            <div className="field-group">
              <PasswordInput
                label="New password"
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
              label="Confirm new password"
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
                ? "Updating…"
                : isGoogleOnlyAccount
                  ? "Set password & sign in"
                  : "Change password"}
            </AuthButton>
            <AuthButton
              type="button"
              variant="secondary"
              fullWidth
              disabled={loading}
              onClick={() => setMode("choice")}
            >
              Back
            </AuthButton>
          </form>
        ) : (
          <div className="auth-choice">
            <p className="auth-choice-hint">
              Your password has not been changed yet. Both options below sign
              you straight into the dashboard.
            </p>
            <AuthButton
              type="button"
              fullWidth
              disabled={loading}
              onClick={() => setMode("change")}
            >
              {isGoogleOnlyAccount ? "Set a password" : "Change password"}
            </AuthButton>
            <AuthButton
              type="button"
              variant="secondary"
              fullWidth
              loading={loading}
              onClick={handleSkip}
            >
              {loading ? "Signing you in…" : "Skip — keep my current password"}
            </AuthButton>
          </div>
        )}
      </AuthCard>
    </AuthLayout>
  );
}

