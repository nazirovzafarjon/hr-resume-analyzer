import { Link } from "react-router-dom";
import { useLanguage } from "../../contexts/LanguageContext";
import { useCandidateAuth } from "../../context/CandidateAuthContext";
import "../../styles/candidate.css";

/**
 * Sits above the (unchanged) public application form and connects it to the
 * Candidate Portal: a signed-in candidate sees that the application will be
 * tracked in their portal; a guest is offered an account first (and can still
 * apply without one, exactly as before).
 */
export default function ApplyAccountBanner({ returnTo }: { returnTo: string }) {
  const { t } = useLanguage();
  const { isAuthenticated, profile } = useCandidateAuth();
  const next = encodeURIComponent(returnTo);

  if (isAuthenticated) {
    return (
      <div className="apply-account-banner" role="note">
        <p>{t("portal.apply.signedIn", { name: profile?.full_name ?? "" })}</p>
        <div className="apply-account-actions">
          <Link className="btn btn--secondary btn--sm" to="/candidate">
            {t("portal.apply.openPortal")}
          </Link>
        </div>
      </div>
    );
  }
  return (
    <div className="apply-account-banner" role="note">
      <p>
        <strong>{t("portal.apply.guestTitle")}</strong> {t("portal.apply.guestMessage")}
      </p>
      <div className="apply-account-actions">
        <Link className="btn btn--primary btn--sm" to={`/candidate/register?next=${next}`}>
          {t("portal.auth.createAccount")}
        </Link>
        <Link className="btn btn--secondary btn--sm" to={`/candidate/login?next=${next}`}>
          {t("portal.auth.signIn")}
        </Link>
      </div>
    </div>
  );
}
