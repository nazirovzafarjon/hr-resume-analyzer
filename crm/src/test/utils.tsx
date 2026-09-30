/**
 * Shared helpers for component tests: fake JWTs and a provider wrapper that
 * mirrors App.tsx (router → auth → theme → language → toasts).
 */
import type { ReactNode } from "react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { render } from "@testing-library/react";
import { AuthProvider } from "../context/AuthContext";
import { ThemeProvider } from "../contexts/ThemeContext";
import { LanguageProvider } from "../contexts/LanguageContext";
import { ToastProvider } from "../contexts/ToastContext";

function base64Url(value: string): string {
  return btoa(value).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

/**
 * A structurally valid, *unsigned* JWT. The frontend only reads the payload
 * for display purposes, which is exactly what these tests exercise; the
 * backend would reject such a token.
 */
export function fakeJwt(payload: Record<string, unknown>): string {
  return [
    base64Url(JSON.stringify({ alg: "HS256", typ: "JWT" })),
    base64Url(JSON.stringify({ sub: "1", typ: "access", ...payload })),
    "signature",
  ].join(".");
}

/** Renders the current pathname so tests can assert redirects. */
export function LocationProbe() {
  const location = useLocation();
  return <div data-testid="location">{location.pathname}</div>;
}

type Options = { path?: string; routes?: { path: string; element: ReactNode }[] };

/** Render `ui` at `path` inside the app providers, plus extra routes. */
export function renderWithProviders(ui: ReactNode, { path = "/", routes = [] }: Options = {}) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <AuthProvider>
        <ThemeProvider>
          <LanguageProvider>
            <ToastProvider>
              <Routes>
                <Route path={path.split("?")[0]} element={ui} />
                {routes.map((route) => (
                  <Route key={route.path} path={route.path} element={route.element} />
                ))}
                <Route path="*" element={<LocationProbe />} />
              </Routes>
            </ToastProvider>
          </LanguageProvider>
        </ThemeProvider>
      </AuthProvider>
    </MemoryRouter>,
  );
}
