import { BrowserRouter, useRoutes, useSearchParams } from "react-router-dom";
import { GoogleOAuthProvider } from "@react-oauth/google";
import type { ReactNode } from "react";
import { AuthProvider } from "./context/AuthContext";
import { StoreProvider } from "./context/StoreContext";
import { ThemeProvider } from "./contexts/ThemeContext";
import { LanguageProvider } from "./contexts/LanguageContext";
import { ToastProvider } from "./contexts/ToastContext";
import { routes } from "./routes";
import ErrorBoundary from "./components/routing/ErrorBoundary";
import Toaster from "./components/ui/Toaster";
import GoogleAuthCallback from "./components/auth/GoogleAuthCallback";
import { GOOGLE_AUTH_ENABLED, GOOGLE_CLIENT_ID } from "./auth/googleConfig";

/**
 * Mounts the Google OAuth provider only when a client id is configured.
 *
 * @react-oauth/google injects Google's GSI script on mount and immediately
 * calls initCodeClient()/initTokenClient(); Google's SDK throws when
 * client_id is empty or missing, which unmounts the whole render tree into a
 * blank screen. Skipping the provider (and therefore the script) entirely
 * keeps email/password auth working when Google is not configured.
 */
function GoogleOAuthGate({ children }: { children: ReactNode }) {
  if (!GOOGLE_AUTH_ENABLED) {
    return <>{children}</>;
  }
  return <GoogleOAuthProvider clientId={GOOGLE_CLIENT_ID}>{children}</GoogleOAuthProvider>;
}

/**
 * Renders the active route from the central route table. The primary OAuth
 * callback is the /oauth/callback route; this also catches a redirect URI that
 * was configured as the bare origin (http://localhost:5173/?code=... or
 * ?error=access_denied) and hands it to the same handler.
 */
function AppRoutes() {
  const [searchParams] = useSearchParams();
  if (searchParams.get("code") || searchParams.get("error")) {
    return <GoogleAuthCallback />;
  }
  return useRoutes(routes);
}

/**
 * Root component: browser router → global error boundary → Google OAuth gate →
 * auth + data providers → theme + language + notifications → route table.
 *
 * <Toaster /> lives outside the route tree so every page (and the shell) can
 * raise notifications without owning any presentation.
 */
export default function App() {
  return (
    <BrowserRouter>
      <ErrorBoundary>
        <GoogleOAuthGate>
          <AuthProvider>
            <StoreProvider>
              <ThemeProvider>
                <LanguageProvider>
                  <ToastProvider>
                    <AppRoutes />
                    <Toaster />
                  </ToastProvider>
                </LanguageProvider>
              </ThemeProvider>
            </StoreProvider>
          </AuthProvider>
        </GoogleOAuthGate>
      </ErrorBoundary>
    </BrowserRouter>
  );
}

