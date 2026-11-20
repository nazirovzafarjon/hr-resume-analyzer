/**
 * Frontend Sentry error reporting utility.
 *
 * Safe and optional: does not throw or fail if VITE_SENTRY_DSN is omitted.
 */

const SENTRY_DSN = import.meta.env.VITE_SENTRY_DSN || "";
const SENTRY_ENV = import.meta.env.VITE_SENTRY_ENVIRONMENT || "production";

/**
 * Capture an unhandled or fatal error and report to Sentry when configured.
 */
export function reportError(error: unknown, context?: Record<string, unknown>): void {
  // Always log locally
  console.error("[observability] Captured frontend error:", error, context);

  if (!SENTRY_DSN) {
    return;
  }

  try {
    // If window Sentry SDK is present (e.g. from CDN or dynamic import)
    const win = window as unknown as { Sentry?: { captureException: (err: unknown, ctx?: unknown) => void } };
    if (win.Sentry && typeof win.Sentry.captureException === "function") {
      win.Sentry.captureException(error, { extra: context });
    }
  } catch (err) {
    console.warn("[observability] Failed to dispatch error to Sentry:", err);
  }
}

export function isSentryEnabled(): boolean {
  return Boolean(SENTRY_DSN);
}

export function getSentryEnvironment(): string {
  return SENTRY_ENV;
}
