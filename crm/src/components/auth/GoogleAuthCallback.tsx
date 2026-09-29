import { useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import AuthLayout from "./AuthLayout";
import AuthCard from "./AuthCard";
import AuthMessage from "./AuthMessage";
import { loginWithGoogle } from "../../services/authService";
import { useAuth } from "../../context/AuthContext";
import { getErrorMessage } from "../../utils/apiError";
import { GOOGLE_REDIRECT_URI } from "../../auth/googleConfig";

/**
 * OAuth callback page (route: /oauth/callback, also reached when the redirect
 * URI is the bare origin with ?code=... or ?error=...).
 *
 * It reads the one-time authorization ``code`` (or an ``error``) from the URL,
 * exchanges the code server-side, stores the JWT via AuthContext and navigates
 * to the dashboard. Every path renders a fallback UI instead of throwing, so a
 * missing, invalid, already-used code or a denied consent can never crash the
 * app into a blank screen.
 */
export default function GoogleAuthCallback() {
  const navigate = useNavigate();
  const { signIn } = useAuth();
  const [serverError, setServerError] = useState<string | null>(null);
  // StrictMode double-invokes effects in development; run the exchange exactly
  // once per mount because an authorization code is single-use.
  const processedRef = useRef(false);

  useEffect(() => {
    if (processedRef.current) return;
    processedRef.current = true;

    const params = new URLSearchParams(window.location.search);
    const oauthError = params.get("error");
    const code = params.get("code");

    if (oauthError) {
      // Google can land us here with ?error=access_denied (user closed the
      // consent screen). Show a friendly message instead of crashing.
      setServerError(
        params.get("error_description") || "Google sign-in was cancelled.",
      );
      return;
    }
    if (!code) {
      setServerError(
        "Google sign-in did not return an authorization code. Please try again.",
      );
      return;
    }
    // Bind the narrowed value once: closures do not keep the `string | null`
    // narrowing of the original const, and the code is single-use anyway.
    const authorizationCode = code;

    // Drop the single-use code from the URL immediately, so a refresh or a
    // shared link can never replay it. Wrapped: some browsers/embeds restrict
    // history manipulation (the exchange still runs).
    try {
      window.history.replaceState(null, "", window.location.pathname);
    } catch {
      /* history manipulation blocked - ignore, the code still works once */
    }

    async function exchange() {
      try {
        // The redirect flow binds the code to the configured callback URL —
        // send it so the backend's token exchange matches exactly.
        const response = await loginWithGoogle(authorizationCode, GOOGLE_REDIRECT_URI);
        signIn(response);
        navigate("/dashboard", { replace: true });
      } catch (err) {
        setServerError(getErrorMessage(err));
      }
    }

    exchange();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const hasError = serverError !== null;
  return (
    <AuthLayout>
      <AuthCard
        title={hasError ? "Google sign-in failed" : "Completing sign-in"}
        subtitle={hasError ? "Your Google account could not be linked." : "Please wait a moment…"}
      >
        {hasError ? (
          <>
            <AuthMessage type="error">{serverError}</AuthMessage>
            <p className="auth-forgot">
              <Link className="auth-link" to="/login">
                Back to sign in
              </Link>
            </p>
          </>
        ) : (
          <p className="auth-subtitle" role="status">
            Verifying your Google account…
          </p>
        )}
      </AuthCard>
    </AuthLayout>
  );
}