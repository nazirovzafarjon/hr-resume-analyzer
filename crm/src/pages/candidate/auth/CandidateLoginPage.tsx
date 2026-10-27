import { useState, type FormEvent } from "react";
import { Link, Navigate, useNavigate, useSearchParams } from "react-router-dom";
import AuthLayout from "../../../components/auth/AuthLayout";
import AuthCard from "../../../components/auth/AuthCard";
import AuthInput from "../../../components/auth/AuthInput";
import PasswordInput from "../../../components/auth/PasswordInput";
import AuthButton from "../../../components/auth/AuthButton";
import AuthMessage from "../../../components/auth/AuthMessage";
import GoogleAuthButton from "../../../components/auth/GoogleAuthButton";
import PageMeta from "../../../components/seo/PageMeta";
import { safeNext } from "../../../components/candidate/safeNext";
import { useCandidateAuth } from "../../../context/CandidateAuthContext";
import { useLanguage } from "../../../contexts/LanguageContext";
import { loginCandidate } from "../../../services/candidatePortalService";
import { ApiError, getErrorMessage } from "../../../utils/apiError";
import { isValidEmail } from "../../../utils/validate";

/** /candidate/login — Candidate Portal sign-in (separate from the HR login). */
export default function CandidateLoginPage() {
  const { t } = useLanguage();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const next = searchParams.get("next");
  const { isAuthenticated, signIn } = useCandidateAuth();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [errors, setErrors] = useState<{ email?: string; password?: string }>({});
  const [serverError, setServerError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  if (isAuthenticated) return <Navigate to={safeNext(next)} replace />;

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const nextErrors: typeof errors = {};
    if (!isValidEmail(email)) nextErrors.email = t("auth.invalidEmail");
    if (!password) nextErrors.password = t("auth.passwordRequired");
    setErrors(nextErrors);
    if (Object.keys(nextErrors).length) return;
    setLoading(true);
    setServerError(null);
    try {
      const result = await loginCandidate({ email: email.trim(), password });
      signIn(result, result.candidate);
      // Unverified candidates must confirm their email before the portal works.
      if (result.candidate.is_email_verified === false) {
        navigate("/candidate/verify-email", {
          replace: true,
          state: { email: email.trim() },
        });
        return;
      }
      navigate(safeNext(next), { replace: true });
    } catch (error) {
      setServerError(
        error instanceof ApiError && error.status === 401 ? error.message : getErrorMessage(error),
      );
    } finally {
      setLoading(false);
    }
  }

  const registerLink = `/candidate/register${next ? `?next=${encodeURIComponent(next)}` : ""}`;

  return (
    <AuthLayout>
      <PageMeta title={t("portal.auth.loginTitle")} />
      <AuthCard
        title={t("portal.auth.loginTitle")}
        subtitle={t("portal.auth.loginSubtitle")}
        footer={
          <>
            {t("portal.auth.noAccount")}{" "}
            <Link className="auth-link" to={registerLink}>
              {t("portal.auth.createAccount")}
            </Link>
            <br />
            <Link className="auth-link" to="/login">
              {t("portal.auth.hrSignIn")}
            </Link>
          </>
        }
      >
        {searchParams.get("expired") === "1" && <AuthMessage type="error">{t("auth.sessionExpired")}</AuthMessage>}
        {serverError && <AuthMessage type="error">{serverError}</AuthMessage>}

        <GoogleAuthButton target="candidate" next={next} disabled={loading} />

        <form className="auth-form" onSubmit={handleSubmit} noValidate>
          <AuthInput
            label={t("auth.email")}
            type="email"
            value={email}
            onChange={setEmail}
            placeholder="you@example.com"
            autoComplete="email"
            error={errors.email}
            disabled={loading}
          />
          <PasswordInput
            label={t("auth.password")}
            value={password}
            onChange={setPassword}
            autoComplete="current-password"
            error={errors.password}
            disabled={loading}
          />
          <AuthButton loading={loading} fullWidth>
            {t("portal.auth.signIn")}
          </AuthButton>
        </form>
        <p className="auth-forgot">
          <Link className="auth-link" to="/candidate/forgot-password">
            {t("auth.forgotPassword")}
          </Link>
        </p>
      </AuthCard>
    </AuthLayout>
  );
}
