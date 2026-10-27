import { useGoogleLogin } from "@react-oauth/google";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { loginWithGoogle } from "../../services/authService";
import { loginCandidateWithGoogle } from "../../services/candidatePortalService";
import { useAuth } from "../../context/AuthContext";
import { useCandidateAuth } from "../../context/CandidateAuthContext";
import { useLanguage } from "../../contexts/LanguageContext";
import { getErrorMessage } from "../../utils/apiError";
import AuthMessage from "./AuthMessage";
import { safeNext } from "../candidate/safeNext";
import {
  GOOGLE_AUTH_ENABLED,
  GOOGLE_AUTH_SCOPES,
  POPUP_FLOW_REDIRECT_URI,
} from "../../auth/googleConfig";

type GoogleAuthButtonProps = {
  /** Disabled while the email/password form is submitting. */
  disabled?: boolean;
  /** Role/portal target for this authentication flow (defaults to "hr"). */
  target?: "hr" | "candidate";
  /** Optional return URL for candidate login redirect. */
  next?: string | null;
};

/**
 * "Continue with Google" button (OAuth 2.0 authorization-code flow).
 *
 * Supports both HR/Admin and Candidate Portal authentication.
 */
export default function GoogleAuthButton({
  disabled = false,
  target = "hr",
  next,
}: GoogleAuthButtonProps) {
  const { t } = useLanguage();
  if (!GOOGLE_AUTH_ENABLED) {
    return null;
  }
  return (
    <>
      <GoogleSignInButton disabled={disabled} target={target} next={next} />
      <div className="auth-divider" role="separator">
        {t("auth.orSignInWithEmail")}
      </div>
    </>
  );
}

function GoogleSignInButton({
  disabled,
  target = "hr",
  next,
}: {
  disabled: boolean;
  target?: "hr" | "candidate";
  next?: string | null;
}) {
  const navigate = useNavigate();
  const hrAuth = useAuth();
  const candidateAuth = useCandidateAuth();
  const { t } = useLanguage();
  const [error, setError] = useState<string | null>(null);

  const googleLogin = useGoogleLogin({
    flow: "auth-code",
    scope: GOOGLE_AUTH_SCOPES,
    overrideScope: true,
    onSuccess: async (response) => {
      try {
        if (target === "candidate") {
          const result = await loginCandidateWithGoogle(
            response.code,
            POPUP_FLOW_REDIRECT_URI,
          );
          candidateAuth.signIn(result, result.candidate);
          navigate(safeNext(next ?? null), { replace: true });
        } else {
          const tokens = await loginWithGoogle(
            response.code,
            POPUP_FLOW_REDIRECT_URI,
          );
          navigate(hrAuth.completeSignIn(tokens));
        }
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
