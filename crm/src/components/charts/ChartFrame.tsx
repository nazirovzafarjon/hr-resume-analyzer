import type { ReactNode } from "react";
import Card from "../ui/Card";
import EmptyState from "../ui/EmptyState";
import Button from "../ui/Button";
import { Skeleton } from "../ui/Skeleton";

type ChartFrameProps = {
  title: string;
  subtitle?: string;
  action?: ReactNode;
  height?: number;
  loading?: boolean;
  error?: string | null;
  onRetry?: () => void;
  isEmpty?: boolean;
  emptyTitle: string;
  emptyMessage: string;
  errorTitle?: string;
  retryLabel?: string;
  children: ReactNode;
};

/**
 * Shared chart shell: title/subtitle/action header (via Card), a skeleton
 * while loading, a recoverable error state, and a meaningful empty state —
 * so every chart on the dashboard behaves the same way at every data state.
 */
export default function ChartFrame({
  title,
  subtitle,
  action,
  height = 280,
  loading = false,
  error,
  onRetry,
  isEmpty = false,
  emptyTitle,
  emptyMessage,
  errorTitle = "Unable to load",
  retryLabel = "Retry",
  children,
}: ChartFrameProps) {
  return (
    <Card title={title} subtitle={subtitle} action={action}>
      {loading ? (
        <div className="chart-state" style={{ height }} aria-hidden="true">
          <Skeleton variant="block" height={height} />
        </div>
      ) : error ? (
        <div className="chart-state">
          <EmptyState
            tone="error"
            title={errorTitle}
            message={error}
            action={onRetry ? <Button onClick={onRetry}>{retryLabel}</Button> : undefined}
          />
        </div>
      ) : isEmpty ? (
        <div className="chart-state">
          <EmptyState title={emptyTitle} message={emptyMessage} />
        </div>
      ) : (
        <div className="chart-canvas" style={{ height }}>
          {children}
        </div>
      )}
    </Card>
  );
}
