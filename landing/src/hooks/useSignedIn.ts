import { useEffect, useState } from "react";
import { SESSION_HINT_COOKIE } from "../lib/config";

function readSignedIn(): boolean {
  return document.cookie
    .split(";")
    .some((part) => part.trim() === `${SESSION_HINT_COOKIE}=1`);
}

/**
 * Whether the visitor has a CRM session, according to the CRM's hint cookie.
 *
 * Re-checked when the tab regains focus or is restored from the back/forward
 * cache, so logging out in the CRM and coming back shows "Log in" again.
 */
export function useSignedIn(): boolean {
  const [signedIn, setSignedIn] = useState(readSignedIn);

  useEffect(() => {
    const update = () => setSignedIn(readSignedIn());
    const onVisibility = () => document.visibilityState === "visible" && update();
    window.addEventListener("pageshow", update);
    document.addEventListener("visibilitychange", onVisibility);
    return () => {
      window.removeEventListener("pageshow", update);
      document.removeEventListener("visibilitychange", onVisibility);
    };
  }, []);

  return signedIn;
}
