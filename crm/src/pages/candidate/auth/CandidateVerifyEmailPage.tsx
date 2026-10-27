import { useLocation, useSearchParams } from "react-router-dom";
import EmailVerificationGate from "../../../components/auth/EmailVerificationGate";
import { CANDIDATE_HOME, useCandidateAuth } from "../../../context/CandidateAuthContext";
import { getCandidateRefreshToken } from "../../../auth/tokenStorage";
import { emailVerifiedFromToken } from "../../../auth/sessionRole";
import {
  refreshCandidateTokens,
  resendCandidateVerification,
  verifyCandidateEmail,
} from "../../../services/candidatePortalService";

/**
 * /candidate/verify-email — the email-verification gate for the Candidate
 * Portal. Same flow as HR, using candidate tokens and endpoints.
 */
export default function CandidateVerifyEmailPage() {
  const [searchParams] = useSearchParams();
  const token = searchParams.get("token");
  const location = useLocation();
  const { signIn } = useCandidateAuth();

  const defaultEmail =
    (location.state as { email?: string } | null)?.email ?? "";

  async function handleVerify(linkToken: string): Promise<string> {
    const result = await verifyCandidateEmail(linkToken);
    signIn(result, result.candidate);
    return CANDIDATE_HOME;
  }

  async function handleResend(email: string): Promise<void> {
    await resendCandidateVerification(email);
  }

  async function handleCheckStatus(): Promise<string | null> {
    // Rotating the refresh token re-reads the account: the new access token
    // carries the current verification claim (the /profile endpoint is gated
    // while unverified, so it cannot be used for this check).
    const refresh = getCandidateRefreshToken();
    if (!refresh) return null;
    const tokens = await refreshCandidateTokens(refresh);
    if (!emailVerifiedFromToken(tokens.access_token)) return null;
    signIn(tokens);
    return CANDIDATE_HOME;
  }

  return (
    <EmailVerificationGate
      token={token}
      defaultEmail={defaultEmail}
      loginPath="/candidate/login"
      onVerify={handleVerify}
      onResend={handleResend}
      onCheckStatus={handleCheckStatus}
    />
  );
}
