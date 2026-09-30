import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { useNavigate } from "react-router-dom";
import {
  clearCandidateTokens,
  getCandidateRefreshToken,
  getCandidateToken,
  saveCandidateTokens,
} from "../auth/tokenStorage";
import { fetchCandidateProfile, logoutCandidate } from "../services/candidatePortalService";
import type { CandidateProfile, CandidateTokens } from "../types/candidatePortal";

type CandidateAuthValue = {
  /** True when a Candidate Portal session is stored. */
  isAuthenticated: boolean;
  /** The signed-in candidate's profile (null while loading or signed out). */
  profile: CandidateProfile | null;
  /** Store a new session (register, login, reset, password change). */
  signIn: (tokens: CandidateTokens, profile?: CandidateProfile) => void;
  /** Replace the cached profile after an edit. */
  setProfile: (profile: CandidateProfile) => void;
  signOut: () => Promise<void>;
};

const CandidateAuthContext = createContext<CandidateAuthValue | undefined>(undefined);

/** Where a candidate lands after signing in. */
export const CANDIDATE_HOME = "/candidate";

/**
 * Candidate Portal session state.
 *
 * Deliberately independent of the HR `AuthProvider`: a candidate is a
 * different identity with different tokens (the backend rejects each token
 * type on the other side), so neither session can leak into the other UI.
 */
export function CandidateAuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(getCandidateToken);
  const [profile, setProfile] = useState<CandidateProfile | null>(null);
  const navigate = useNavigate();

  const signIn = useCallback((tokens: CandidateTokens, nextProfile?: CandidateProfile) => {
    saveCandidateTokens(tokens.access_token, tokens.refresh_token);
    setToken(tokens.access_token);
    if (nextProfile) setProfile(nextProfile);
  }, []);

  const signOut = useCallback(async () => {
    const refreshToken = getCandidateRefreshToken();
    try {
      if (getCandidateToken()) await logoutCandidate(refreshToken);
    } catch {
      // The session is being dropped anyway; a failed revoke is not fatal.
    }
    clearCandidateTokens();
    setToken(null);
    setProfile(null);
  }, []);

  // Load the profile for a stored session (e.g. after a page reload).
  useEffect(() => {
    if (!token || profile) return;
    let current = true;
    fetchCandidateProfile()
      .then((result) => {
        if (current) setProfile(result);
      })
      .catch(() => {
        // A dead session is handled by the "candidate:unauthorized" event.
      });
    return () => {
      current = false;
    };
  }, [token, profile]);

  // The API client broadcasts this when a candidate request still fails after
  // its silent refresh: drop the session and go back to the portal sign-in.
  useEffect(() => {
    function handleUnauthorized() {
      clearCandidateTokens();
      setToken(null);
      setProfile(null);
      navigate("/candidate/login?expired=1");
    }
    window.addEventListener("candidate:unauthorized", handleUnauthorized);
    return () => window.removeEventListener("candidate:unauthorized", handleUnauthorized);
  }, [navigate]);

  return (
    <CandidateAuthContext.Provider
      value={{ isAuthenticated: token !== null, profile, signIn, setProfile, signOut }}
    >
      {children}
    </CandidateAuthContext.Provider>
  );
}

export function useCandidateAuth(): CandidateAuthValue {
  const context = useContext(CandidateAuthContext);
  if (!context) throw new Error("useCandidateAuth must be used within a CandidateAuthProvider");
  return context;
}
