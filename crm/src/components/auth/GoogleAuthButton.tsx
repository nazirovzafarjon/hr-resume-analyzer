import { useGoogleLogin } from "@react-oauth/google";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { loginWithGoogle } from "../../services/authService";
import { useAuth } from "../../context/AuthContext";
import { useLanguage } from "../../contexts/LanguageContext";
import { getErrorMessage } from "../../utils/apiError";
import AuthMessage from "./AuthMessage";
import {
  GOOGLE_AUTH_ENABLED,
  GOOGLE_AUTH_SCOPES,
  POPUP_FLOW_REDIRECT_URI,
} from "../../auth/googleConfig";

type GoogleAuthButtonProps = {
  /** Disabled while the email/password form is submitting. */
  disabled?: boolean;
};

/**
 * "Continue with Google" button (OAuth 2.0 authorization-code flow).
 *
 * Renders nothing when Google is not configured - the auth UI degrades cleanly
 * to email/password instead of touching Google's scripts. When configured,
 * clicking starts Google's redirect flow; the browser lands back on
 * /oauth/callback with a one-time ``code`` that GoogleAuthCallback exchanges
 * server-side.
 */
export default function GoogleAuthButton({ disabled = false }: GoogleAuthButtonProps) {
  const { t } = useLanguage();
  if (!GOOGLE_AUTH_ENABLED) {
    return null;
  }
  return (
    <>
      <GoogleSignInButton disabled={disabled} />
      <div className="auth-divider" role="separator">
        {t("auth.orSignInWithEmail")}
      </div>
    </>
  );
}

/**
 * Inner component that owns the OAuth hook. Kept separate so the hook is only
 * ever called while GoogleOAuthProvider is actually mounted (GoogleOAuthGate
 * in App.tsx mounts it iff GOOGLE_AUTH_ENABLED).
 *
 * Popup UX (the default): Google's JS client binds the authorization code to
 * the special redirect_uri "postmessage" (the `redirect_uri` option below is
 * ignored for popups), so the code is sent to the backend together with
 * POPUP_FLOW_REDIRECT_URI so the server-side exchange matches exactly — a
 * mismatch makes Google fail the exchange with invalid_grant.
 */
function GoogleSignInButton({ disabled }: { disabled: boolean }) {
  const navigate = useNavigate();
  const { completeSignIn } = useAuth();
  const { t } = useLanguage();
  const [error, setError] = useState<string | null>(null);

  const googleLogin = useGoogleLogin({
    flow: "auth-code",
    // Explicitly request the identity scopes so the backend receives
    // sub / email / name / picture from the userinfo endpoint (see
    // GOOGLE_AUTH_SCOPES in auth/googleConfig.ts).
    scope: GOOGLE_AUTH_SCOPES,
    overrideScope: true,
    onSuccess: async (response) => {
      try {
        const tokens = await loginWithGoogle(
          response.code,
          POPUP_FLOW_REDIRECT_URI,
        );
        // Straight into the workspace, or to the workspace choice.
        navigate(completeSignIn(tokens));
      } catch (err) {
        setError(getErrorMessage(err));
      }
    },
    onError: (errorResponse) => {
      setError(errorResponse.error_description || t("auth.googleSignInFailed"));
    },
    onNonOAuthError: (nonOAuthError) => {
      setError(
        nonOAuthError.type === "popup_failed_to_open"
          ? t("auth.googlePopupBlocked")
          : t("auth.googleCancelled"),
      );
    },
  });

  return (
    <>
      {error && <AuthMessage type="error">{error}</AuthMessage>}
      <button
        type="button"
        className="btn btn--google btn--block"
        disabled={disabled}
        onClick={() => {
          setError(null);
          googleLogin();
        }}
      >
        <GoogleLogo />
        <span>{t("auth.continueWithGoogle")}</span>
      </button>
    </>
  );
}

/** Official Google "G" mark (four-color) per Google's sign-in brand guidelines. */
function GoogleLogo() {
  return (
    <svg
      className="google-logo"
      width="20"
      height="20"
      viewBox="0 0 48 48"
      aria-hidden="true"
    >
      <path
        fill="#EA4335"
        d="M24 4C19.6 4 15.8 5.8 13.1 8.7l5.3 4.1C20.1 11.2 21.9 10 24 10c4.4 0 8.2 3.2 9 7.5l5.3-4.1C34.9 6.6 29.7 4 24 4z"
      />
      <path
        fill="#4285F4"
        d="M24 44c5.6 0 10.8-2.4 14.6-6.2l-5.5-4.3c-2.7 1.9-6 3-9.1 3-3.4 0-6.4-1.2-8.8-3.2l-7.3 5.6C9.2 39.6 16.3 44 24 44z"
      />
      <path
        fill="#34A856"
        d="M4.4 23.9c-.1.7-.1 1.4 0 2.2l7.6 5.9c-2.2 2.2-5.3 3.7-8.7 4v-5.6L4.4 23.9z"
      />
      <path
        fill="#FBBC05"
        d="M12.5 16.5c-.3 1.4-.3 2.8 0 4.2L8.2 24c-1.8-3.5-1.8-7.7 0-11.2l4.3 0z"
      />
    </svg>
  );
}
