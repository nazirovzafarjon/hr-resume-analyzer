/**
 * Error handling for API requests.
 *
 * `ApiError` carries an HTTP status so callers can branch on it (e.g. show
 * "Invalid email or password" only for a 401 on login). `getErrorMessage`
 * turns any thrown value into a safe, user-friendly message without ever
 * leaking stack traces or backend internals.
 */

/** Raised by the API client whenever a request does not succeed. */
export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

const NETWORK_MESSAGE =
  "Unable to connect to the server. Please check your connection and try again.";
const SERVER_MESSAGE = "Something went wrong. Please try again.";

/**
 * Map any thrown value to a user-facing message.
 *
 * - Network failures (status 0) and server errors (5xx) are always generic.
 * - Client errors (4xx) may surface the backend's `detail`, which is a
 *   meaningful message (e.g. "A user with this email already exists").
 */
export function getErrorMessage(
  error: unknown,
  fallback = SERVER_MESSAGE,
): string {
  if (error instanceof ApiError) {
    if (error.status === 0 || error.status >= 500) {
      return error.status === 0 ? NETWORK_MESSAGE : SERVER_MESSAGE;
    }
    return error.message || fallback;
  }
  return fallback;
}
