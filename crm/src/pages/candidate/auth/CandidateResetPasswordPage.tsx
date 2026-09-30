import { useState, type FormEvent } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import AuthLayout from "../../../components/auth/AuthLayout";
import AuthCard from "../../../components/auth/AuthCard";
import PasswordInput from "../../../components/auth/PasswordInput";
import AuthButton from "../../../components/auth/AuthButton";
import AuthMessage from "../../../components/auth/AuthMessage";
import PageMeta from "../../../components/seo/PageMeta";
import { CANDIDATE_HOME, useCandidateAuth } from "../../../context/CandidateAuthContext";
import { useLanguage } from "../../../contexts/LanguageContext";
import { resetCandidatePassword } from "../../../services/candidatePortalService";
import { getErrorMessage } from "../../../utils/apiError";

const PASSWORD_MIN = 8;
const PASSWORD_MAX = 72;

/** /candidate/reset-password?token=… — set a new password from the emailed link. */
export default function CandidateResetPasswordPage() {
  const { t } = useLanguage();
  const navigate = useNavigate();
  const token = useSearchParams()[0].get("token") ?? "";
  const { signIn } = useCandidateAuth();
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (password.length < PASSWORD_MIN || password.length > PASSWORD_MAX) {
      return setError(t("portal.auth.passwordRule", { min: PASSWORD_MIN, max: PASSWORD_MAX }));
    }
    setLoading(true);
    setError(null);
    try {
      const result = await resetCandidatePassword(token, password);
      signIn(result, result.candidate);
      navigate(CANDIDATE_HOME, { replace: true });
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }

  return (
    <AuthLayout>
      <PageMeta title={t("portal.auth.resetTitle")} noindex />
      <AuthCard
        title={t("portal.auth.resetTitle")}
        footer={
          <Link className="auth-link" to="/candidate/forgot-password">
            {t("portal.auth.requestNewLink")}
          </Link>
        }
      >
        {!token ? (
          <AuthMessage type="error">{t("portal.auth.resetMissingToken")}</AuthMessage>
        ) : (
          <form className="auth-form" onSubmit={handleSubmit} noValidate>
            {error && <AuthMessage type="error">{error}</AuthMessage>}
            <PasswordInput label={t("portal.profile.newPassword")} value={password} onChange={setPassword} autoComplete="new-password" disabled={loading} />
            <AuthButton loading={loading} fullWidth>
              {t("portal.auth.setPassword")}
            </AuthButton>
          </form>
        )}
      </AuthCard>
    </AuthLayout>
  );
}
