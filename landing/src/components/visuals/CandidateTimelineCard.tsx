import { Check } from "lucide-react";
import { useI18n } from "../../i18n";

/**
 * Illustration of the Candidate Portal's application timeline. Sample data
 * only (labelled as such by the caller); the real portal builds it from the
 * application's recorded history.
 */
export default function CandidateTimelineCard() {
  const { t } = useI18n();
  const sample = t.candidates.sample;
  return (
    <div className="card timeline-card" role="img" aria-label={sample.label}>
      <div className="timeline-card-head">
        <div>
          <p className="timeline-card-role">{sample.role}</p>
          <p className="timeline-card-company">{sample.company}</p>
        </div>
        <span className="timeline-card-status">{sample.status}</span>
      </div>
      <ol className="timeline-card-steps">
        {sample.steps.map((step, index) => {
          const state = index < 2 ? "done" : index === 2 ? "current" : "upcoming";
          return (
            <li key={step.title} className={`timeline-card-step timeline-card-step--${state}`}>
              <span className="timeline-card-marker" aria-hidden="true">
                {state === "done" && <Check size={12} />}
              </span>
              <span>
                <strong>{step.title}</strong>
                <span>{step.meta}</span>
              </span>
            </li>
          );
        })}
      </ol>
      <div className="timeline-card-match">
        <span>{sample.matchLabel}</span>
        <strong>{sample.match}</strong>
      </div>
    </div>
  );
}
