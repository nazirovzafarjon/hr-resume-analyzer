import { useState, type FormEvent } from "react";
import { Link, Navigate, useNavigate, useSearchParams } from "react-router-dom";
import AuthLayout from "../../../components/auth/AuthLayout";
import AuthCard from "../../../components/auth/AuthCard";
import AuthInput from "../../../components/auth/AuthInput";
import PasswordInput from "../../../components/auth/PasswordInput";
import AuthButton from "../../../components/auth/AuthButton";
import AuthMessage from "../../../components/auth/AuthMessage";
import PageMeta from "../../../components/seo/PageMeta";
import { safeNext } from "../../../components/candidate/safeNext";
import { useCandidateAuth } from "../../../context/CandidateAuthContext";
import { useLanguage } from "../../../contexts/LanguageContext";
import { registerCandidate } from "../../../services/candidatePortalService";
import { getErrorMessage } from "../../../utils/apiError";
import { isValidEmail } from "../../../utils/validate";

const PASSWORD_MIN = 8;
const PASSWORD_MAX = 72;

type Errors = { fullName?: string; email?: string; password?: string };

/** /candidate/register — create a Candidate Portal account. */
export default function CandidateRegisterPage() {
  const { t } = useLanguage();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const next = searchParams.get("next");
  const { isAuthenticated, signIn } = useCandidateAuth();

  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [errors, setErrors] = useState<Errors>({});
  const [serverError, setServerError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  if (isAuthenticated) return <Navigate to={safeNext(next)} replace />;

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const nextErrors: Errors = {};
    if (!fullName.trim()) nextErrors.fullName = t("portal.profile.nameRequired");
    if (!isValidEmail(email)) nextErrors.email = t("auth.invalidEmail");
    if (password.length < PASSWORD_MIN || password.length > PASSWORD_MAX) {
      nextErrors.password = t("portal.auth.passwordRule", { min: PASSWORD_MIN, max: PASSWORD_MAX });
    }
    setErrors(nextErrors);
    if (Object.keys(nextErrors).length) return;
    setLoading(true);
    setServerError(null);
    try {
      const result = await registerCandidate({ full_name: fullName.trim(), email: email.trim(), password });
      signIn(result, result.candidate);
      navigate(safeNext(next), { replace: true });
    } catch (error) {
      setServerError(getErrorMessage(error));
    } finally {
      setLoading(false);
    }
  }

  const loginLink = `/candidate/login${next ? `?next=${encodeURIComponent(next)}` : ""}`;

  return (
    <AuthLayout>
      <PageMeta title={t("portal.auth.registerTitle")} />
      <AuthCard
        title={t("portal.auth.registerTitle")}
        subtitle={t("portal.auth.registerSubtitle")}
        footer={
          <>
            {t("portal.auth.haveAccount")}{" "}
            <Link className="auth-link" to={loginLink}>
              {t("portal.auth.signIn")}
            </Link>
          </>
        }
      >
        {serverError && <AuthMessage type="error">{serverError}</AuthMessage>}
        <form className="auth-form" onSubmit={handleSubmit} noValidate>
          <AuthInput
            label={t("portal.profile.fullName")}
            value={fullName}
            onChange={setFullName}
            autoComplete="name"
            error={errors.fullName}
            disabled={loading}
          />
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
            autoComplete="new-password"
            error={errors.password}
            disabled={loading}
          />
          <p className="auth-subtitle" style={{ margin: 0 }}>
            {t("portal.auth.passwordRule", { min: PASSWORD_MIN, max: PASSWORD_MAX })}
          </p>
          <AuthButton loading={loading} fullWidth>
            {t("portal.auth.createAccount")}
          </AuthButton>
        </form>
      </AuthCard>
    </AuthLayout>
  );
}
