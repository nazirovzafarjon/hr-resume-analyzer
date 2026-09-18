import { AI_PROCESSING_STEPS } from "../../data/mock/jobAi";

/**
 * Simulated AI checklist shown while a vacancy is being analysed.
 * `doneCount` is the number of completed steps (0..steps.length).
 */
export default function AIProcessingCard({ doneCount }: { doneCount: number }) {
  return (
    <div className="ai-processing" role="status" aria-label="AI is analysing the vacancy">
      <div className="ai-processing-header">
        <span className="btn-spinner" aria-hidden="true" />
        <div>
          <h3>AI is analysing your vacancy…</h3>
          <p>This usually takes a few seconds in the demo.</p>
        </div>
      </div>
      <ul className="ai-steps">
        {AI_PROCESSING_STEPS.map((step, index) => {
          const done = index < doneCount;
          const active = index === doneCount;
          return (
            <li key={step} className={done ? "is-done" : active ? "is-active" : ""}>
              <span className="ai-step-icon" aria-hidden="true">
                {done ? "✓" : active ? "…" : "○"}
              </span>
              {step}
            </li>
          );
        })}
      </ul>
    </div>
  );
}
