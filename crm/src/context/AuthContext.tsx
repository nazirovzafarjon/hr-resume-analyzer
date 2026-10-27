import {
  createContext,
  useCallback,
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
import { emailVerifiedFromToken, roleFromToken } from "../auth/sessionRole";
import {
  SESSION_ROLES,
  type AuthResponse,
  type RoleSelectionRequired,
  type SessionRole,
  type SignInResult,
} from "../types/auth";
import { selectRole as selectRoleRequest, switchRole as switchRoleRequest } from "../services/authService";
import { invalidateCurrentUser } from "../hooks/useCurrentUser";

/** A sign-in that is waiting for the user to pick a workspace. */
export type PendingRoleSelection = {
  selectionToken: string;
  availableRoles: SessionRole[];
  fullName: string;
  /** Epoch ms after which the selection token is no longer accepted. */
  expiresAt: number;
};

type AuthContextValue = {
  /** True when a session (access JWT) is currently stored. */
  isAuthenticated: boolean;
  /**
   * Workspace of the current session, read from the server-signed token.
   * Only decides what the UI shows; the backend enforces it on every request.
   */
  activeRole: SessionRole | null;
  /**
   * Email-verification state of the current session, read from the token.
   * UI-only: the backend re-checks the flag on every panel request.
   */
  isEmailVerified: boolean;
  /** Set between a multi-role sign-in and the workspace choice. */
  pendingSelection: PendingRoleSelection | null;
  /**
   * Handle any sign-in response (login, register, Google, password reset):
   * store the session, or remember the pending workspace choice. Returns the
   * path to navigate to next.
   */
  completeSignIn: (result: SignInResult) => string;
  /** Store a freshly issued access/refresh pair (e.g. after a password change). */
  signIn: (tokens: AuthResponse) => void;
  /** Finish a pending sign-in in the chosen workspace; returns the landing path. */
  selectRole: (role: SessionRole) => Promise<string>;
  /** Move the current session to another workspace; returns the landing path. */
  switchRole: (role: SessionRole) => Promise<string>;
  /** Clear the session, any pending choice and cached profile. */
  signOut: () => void;
};

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

/** Where a session of the given workspace starts. */
export function landingPath(role: SessionRole | null): string {
  return role === SESSION_ROLES.ADMIN ? "/admin/dashboard" : "/dashboard";
}

function isSelection(result: SignInResult): result is RoleSelectionRequired {
  return result.requires_role_selection === true;
}

/**
 * Owns the app-wide authentication state — the single source of truth for
 * "signed in?", "which workspace?" and "waiting for a workspace choice?".
 *
 * The JWTs live in localStorage (see tokenStorage). The pending workspace
 * choice deliberately lives in memory only: its selection token is a
 * short-lived credential, so a page reload simply means signing in again.
 */
export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(getToken);
  const [pendingSelection, setPendingSelection] = useState<PendingRoleSelection | null>(null);
  const navigate = useNavigate();

  // The cached profile (and with it the workspace) belongs to the previous
  // session, so it is dropped whenever the session may change.
  const signIn = useCallback((tokens: AuthResponse) => {
    invalidateCurrentUser();
    setPendingSelection(null);
    saveTokens(tokens.access_token, tokens.refresh_token);
    setToken(tokens.access_token);
  }, []);

  const signOut = useCallback(() => {
    invalidateCurrentUser();
    setPendingSelection(null);
    clearToken();
    setToken(null);
  }, []);

  const completeSignIn = useCallback(
    (result: SignInResult): string => {
      if (isSelection(result)) {
        // A new sign-in replaces whatever session was stored before.
        invalidateCurrentUser();
        clearToken();
        setToken(null);
        setPendingSelection({
          selectionToken: result.selection_token,
          availableRoles: result.available_roles,
          fullName: result.full_name,
          expiresAt: Date.now() + result.expires_in * 1000,
        });
        return "/select-role";
      }
      signIn(result);
      return landingPath(roleFromToken(result.access_token));
    },
    [signIn],
  );

  const selectRole = useCallback(
    async (role: SessionRole): Promise<string> => {
      if (!pendingSelection) throw new Error("No workspace choice is pending.");
      const tokens = await selectRoleRequest(pendingSelection.selectionToken, role);
      signIn(tokens);
      return landingPath(roleFromToken(tokens.access_token));
    },
    [pendingSelection, signIn],
  );

  const switchRole = useCallback(
    async (role: SessionRole): Promise<string> => {
      const tokens = await switchRoleRequest(role);
      signIn(tokens);
      return landingPath(roleFromToken(tokens.access_token));
    },
    [signIn],
  );

  // Publish the signed-in hint for the landing site ("Open workspace").
  useEffect(syncSessionHint, []);

  // When a protected API request still fails after the client's silent refresh
  // attempt, the API client clears the tokens and broadcasts this event. React
  // to it here (single place) so the user is sent back to login instead of
  // being stuck on a broken authenticated page.
  useEffect(() => {
    function handleUnauthorized() {
      invalidateCurrentUser();
      setPendingSelection(null);
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
      value={{
        isAuthenticated: token !== null,
        activeRole: token ? roleFromToken(token) : null,
        isEmailVerified: token ? emailVerifiedFromToken(token) : false,
        pendingSelection,
        completeSignIn,
        signIn,
        selectRole,
        switchRole,
        signOut,
      }}
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
