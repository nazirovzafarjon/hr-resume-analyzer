import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { useCandidateAuth } from "../../context/CandidateAuthContext";

/**
 * Guards Candidate Portal pages: without a candidate session the visitor goes
 * to the portal sign-in (and comes back afterwards). An HR session does not
 * count. This is UX only; every /api/candidate endpoint checks the token.
 */
export default function RequireCandidate({ children }: { children: ReactNode }) {
  const { isAuthenticated, isEmailVerified } = useCandidateAuth();
  const location = useLocation();
  if (!isAuthenticated) {
    const next = encodeURIComponent(location.pathname + location.search);
    return <Navigate to={`/candidate/login?next=${next}`} replace />;
  }
  // The portal needs a confirmed email (backend enforces it too).
  if (!isEmailVerified) {
    return <Navigate to="/candidate/verify-email" replace />;
  }
  return <>{children}</>;
}
