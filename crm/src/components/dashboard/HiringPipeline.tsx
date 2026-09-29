import EmptyState from "../ui/EmptyState";
import { Skeleton } from "../ui/Skeleton";
import type { StatusTone } from "../../utils/statusLabels";

export type PipelineStage = {
  status: string;
  label: string;
  tone: StatusTone;
  count: number;
  /** Rejected / withdrawn — rendered separately from the forward flow. */
  isTerminal?: boolean;
};

type HiringPipelineProps = {
  stages: PipelineStage[];
  loading?: boolean;
  emptyTitle: string;
  emptyMessage: string;
};

/**
 * Ordered hiring-stage flow, sourced directly from the real application-status
 * distribution — no invented conversion rates, just counts and their share of
 * the total pipeline.
 */
export default function HiringPipeline({ stages, loading = false, emptyTitle, emptyMessage }: HiringPipelineProps) {
  if (loading) {
    return (
      <ol className="pipeline-list" aria-hidden="true">
        {Array.from({ length: 5 }).map((_, index) => (
          <li key={index} className="pipeline-stage">
            <Skeleton width="55%" height={10} />
            <Skeleton width="30%" height={20} style={{ marginTop: "var(--space-xs)" }} />
          </li>
        ))}
      </ol>
    );
  }

  const total = stages.reduce((sum, stage) => sum + stage.count, 0);
  if (total === 0) {
    return <EmptyState title={emptyTitle} message={emptyMessage} />;
  }

  return (
    <ol className="pipeline-list">
      {stages.map((stage) => (
        <li
          key={stage.status}
          className={`pipeline-stage${stage.isTerminal ? " pipeline-stage--terminal" : ""}`}
        >
          <span className={`pipeline-dot pipeline-dot--${stage.tone}`} aria-hidden="true" />
          <span className="pipeline-label">{stage.label}</span>
          <span className="pipeline-count">{stage.count}</span>
          <span className="pipeline-percent">{Math.round((stage.count / total) * 100)}%</span>
        </li>
      ))}
    </ol>
  );
}
