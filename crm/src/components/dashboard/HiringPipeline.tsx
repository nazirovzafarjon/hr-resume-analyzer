import { Fragment } from "react";
import EmptyState from "../ui/EmptyState";
import { Skeleton } from "../ui/Skeleton";

export type PipelineStage = {
  status: string;
  label: string;
  count: number;
  /** Rejected / withdrawn — rendered after a divider, in a muted colour. */
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
 * distribution — no invented conversion rates, just counts, a bar scaled to
 * the largest stage and each stage's share of the total.
 */
export default function HiringPipeline({ stages, loading = false, emptyTitle, emptyMessage }: HiringPipelineProps) {
  if (loading) {
    return (
      <ol className="pipeline-list" aria-hidden="true">
        {Array.from({ length: 5 }).map((_, index) => (
          <li key={index} className="pipeline-stage">
            <Skeleton width="70%" height={10} />
            <Skeleton width={`${80 - index * 12}%`} height={8} />
          </li>
        ))}
      </ol>
    );
  }

  const total = stages.reduce((sum, stage) => sum + stage.count, 0);
  if (total === 0) {
    return <EmptyState title={emptyTitle} message={emptyMessage} />;
  }
  const max = Math.max(...stages.map((stage) => stage.count));
  const firstTerminal = stages.findIndex((stage) => stage.isTerminal);

  return (
    <ol className="pipeline-list">
      {stages.map((stage, index) => (
        <Fragment key={stage.status}>
          {index === firstTerminal && index > 0 && <li className="pipeline-divider" aria-hidden="true" />}
          <li className={`pipeline-stage${stage.isTerminal ? " pipeline-stage--terminal" : ""}`}>
            <span className="pipeline-label" title={stage.label}>{stage.label}</span>
            <span className="pipeline-track" aria-hidden="true">
              <span className="pipeline-bar" style={{ width: `${(stage.count / max) * 100}%` }} />
            </span>
            <span className="pipeline-count">{stage.count}</span>
            <span className="pipeline-percent">{Math.round((stage.count / total) * 100)}%</span>
          </li>
        </Fragment>
      ))}
    </ol>
  );
}
