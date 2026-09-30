import { useEffect, useState } from "react";
import { getCurrentUser } from "../services/settingsService";
import type { UserProfile } from "../types/user";

/**
 * The signed-in user's profile, fetched once and shared.
 *
 * Several places need to know whether the user is an administrator (the admin
 * route guard, the sidebar and header links). Sharing one in-flight request
 * avoids hitting /auth/me once per component. The cache is dropped on sign-in
 * and sign-out (see AuthContext) so a different account never sees a stale
 * role.
 */
let cached: Promise<UserProfile> | null = null;

export function invalidateCurrentUser(): void {
  cached = null;
}

function loadCurrentUser(): Promise<UserProfile> {
  cached ??= getCurrentUser().catch((error: unknown) => {
    cached = null; // let the next caller retry
    throw error;
  });
  return cached;
}

type CurrentUserState = {
  user: UserProfile | null;
  loading: boolean;
  error: unknown;
};

export function useCurrentUser(): CurrentUserState {
  const [state, setState] = useState<CurrentUserState>({ user: null, loading: true, error: null });

  useEffect(() => {
    let cancelled = false;
    loadCurrentUser()
      .then((user) => {
        if (!cancelled) setState({ user, loading: false, error: null });
      })
      .catch((error: unknown) => {
        if (!cancelled) setState({ user: null, loading: false, error });
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return state;
}
