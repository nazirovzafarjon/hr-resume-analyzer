import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import AuthLayout from "../../../components/auth/AuthLayout";
import AuthCard from "../../../components/auth/AuthCard";
import AuthInput from "../../../components/auth/AuthInput";
import AuthButton from "../../../components/auth/AuthButton";
import AuthMessage from "../../../components/auth/AuthMessage";
import PageMeta from "../../../components/seo/PageMeta";
import { useLanguage } from "../../../contexts/LanguageContext";
import { requestCandidatePasswordReset } from "../../../services/candidatePortalService";
import { getErrorMessage } from "../../../utils/apiError";
import { isValidEmail } from "../../../utils/validate";

/** /candidate/forgot-password — the same answer for every address. */
export default function CandidateForgotPasswordPage() {
  const { t } = useLanguage();
  const [email, setEmail] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [sent, setSent] = useState(false);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!isValidEmail(email)) return setError(t("auth.invalidEmail"));
    setLoading(true);
    setError(null);
    try {
      await requestCandidatePasswordReset(email.trim());
      setSent(true);
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }

  return (
    <AuthLayout>
      <PageMeta title={t("portal.auth.forgotTitle")} />
      <AuthCard
        title={t("portal.auth.forgotTitle")}
        subtitle={t("portal.auth.forgotSubtitle")}
        footer={
          <Link className="auth-link" to="/candidate/login">
            {t("portal.auth.backToSignIn")}
          </Link>
        }
      >
        {sent ? (
          <AuthMessage type="success">{t("portal.auth.forgotSent")}</AuthMessage>
        ) : (
          <form className="auth-form" onSubmit={handleSubmit} noValidate>
            {error && <AuthMessage type="error">{error}</AuthMessage>}
            <AuthInput label={t("auth.email")} type="email" value={email} onChange={setEmail} autoComplete="email" disabled={loading} />
            <AuthButton loading={loading} fullWidth>
              {t("portal.auth.sendLink")}
            </AuthButton>
          </form>
        )}
      </AuthCard>
    </AuthLayout>
  );
}
