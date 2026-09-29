import {
  createContext,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import { useNavigate } from "react-router-dom";
import {
  clearToken,
  getToken,
  saveTokens,
  syncSessionHint,
} from "../auth/tokenStorage";
import type { AuthResponse } from "../types/auth";

type AuthContextValue = {
  /** True when a JWT is currently stored. */
  isAuthenticated: boolean;
  /**
   * Store a freshly issued access/refresh pair after login, registration,
   * Google sign-in, a password reset or the reset page's "Skip" action.
   */
  signIn: (tokens: AuthResponse) => void;
  /** Clear the JWTs after logout or session expiry. */
  signOut: () => void;
};

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

/**
 * Owns the app-wide authentication state. The JWTs live in localStorage (see
 * tokenStorage); this provider keeps the in-memory React state in sync so the
 * whole app reflects whether a user is signed in. State is initialized once on
 * mount from the stored token, so no per-render API calls are made.
 */
export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(getToken);
  const navigate = useNavigate();

  function signIn(tokens: AuthResponse) {
    saveTokens(tokens.access_token, tokens.refresh_token);
    setToken(tokens.access_token);
  }

  function signOut() {
    clearToken();
    setToken(null);
  }

  // Publish the signed-in hint for the landing site ("Open workspace").
  useEffect(syncSessionHint, []);

  // When a protected API request still fails after the client's silent refresh
  // attempt, the API client clears the tokens and broadcasts this event. React
  // to it here (single place) so the user is sent back to login instead of
  // being stuck on a broken authenticated page.
  useEffect(() => {
    function handleUnauthorized() {
      clearToken();
      setToken(null);
      navigate("/login?expired=1");
    }
    window.addEventListener("auth:unauthorized", handleUnauthorized);
    return () =>
      window.removeEventListener("auth:unauthorized", handleUnauthorized);
  }, [navigate]);

  return (
    <AuthContext.Provider
      value={{ isAuthenticated: token !== null, signIn, signOut }}
    >
      {children}
    </AuthContext.Provider>
  );
}

/** Access the shared authentication state; must be used within an AuthProvider. */
export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
