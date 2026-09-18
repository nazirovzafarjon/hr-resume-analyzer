import { Component, type ReactNode } from "react";
import { AlertTriangle } from "lucide-react";

type ErrorBoundaryProps = { children: ReactNode };
type ErrorBoundaryState = { error: Error | null };

/**
 * Catches uncaught render/effect errors below it and shows a recoverable error
 * card instead of letting the whole app unmount into a blank screen.
 *
 * Without a boundary a single runtime error - a broken third-party script, a
 * provider that throws during mount, a bad localStorage value - takes down the
 * entire UI with no way back. The boundary also always logs the full error so
 * developers keep the details without exposing them in the UI.
 */
export default class ErrorBoundary extends Component<
  ErrorBoundaryProps,
  ErrorBoundaryState
> {
  state: ErrorBoundaryState = { error: null };

  /** React calls this when a child throws during render. */
  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { error };
  }

  override componentDidUpdate(
    _prevProps: ErrorBoundaryProps,
    prevState: ErrorBoundaryState,
  ): void {
    if (this.state.error && this.state.error !== prevState.error) {
      console.error("[error-boundary] fatal error:", this.state.error);
    }
  }

  override render(): ReactNode {
    if (this.state.error) {
      return (
        <div className="error-boundary" role="alert">
          <span className="error-boundary-icon" aria-hidden="true">
            <AlertTriangle size={22} />
          </span>
          <h1>Something went wrong</h1>
          <p>
            The application hit an unexpected error. Reload the page to continue —
            your data is safe.
          </p>
          <button type="button" className="btn" onClick={() => window.location.reload()}>
            Reload page
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
