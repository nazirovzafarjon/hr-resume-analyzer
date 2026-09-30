import { Check, Circle, Dot, Minus } from "lucide-react";
import { useLanguage } from "../../contexts/LanguageContext";
import type { TimelineStep } from "../../types/candidatePortal";
import { portalDate, portalDateTime } from "./portalFormat";

const ICONS = {
  done: <Check size={15} aria-hidden="true" />,
  current: <Dot size={22} aria-hidden="true" />,
  upcoming: <Circle size={8} aria-hidden="true" />,
  skipped: <Minus size={14} aria-hidden="true" />,
  unavailable: <Minus size={14} aria-hidden="true" />,
};

/**
 * "What is happening with my application?" — the five steps from the API.
 * Dates are shown only when the backend knows the real moment. Each state has
 * its own icon and text, not just a colour.
 */
export default function ApplicationTimeline({ steps }: { steps: TimelineStep[] }) {
  const { t } = useLanguage();

  function title(step: TimelineStep): string {
    if (step.key === "decision" && step.outcome) return t(`portal.timeline.decision_${step.outcome}`);
    return t(`portal.timeline.${step.key}`);
  }

  function meta(step: TimelineStep): string {
    if (step.date) {
      const when = step.key === "interview" ? portalDateTime(step.date) : portalDate(step.date);
      return step.key === "interview" && step.state === "current"
        ? t("portal.timeline.scheduledFor", { date: when })
        : when;
    }
    return t(`portal.timeline.state.${step.state}${step.key === "resume_review" ? "Resume" : ""}`);
  }

  return (
    <ol className="portal-timeline">
      {steps.map((step) => (
        <li
          key={step.key}
          className={`portal-timeline-step portal-timeline-step--${step.state}`}
          aria-current={step.state === "current" ? "step" : undefined}
        >
          <span className="portal-timeline-marker">{ICONS[step.state]}</span>
          <div>
            <p className="portal-timeline-title">
              {title(step)}
              <span className="sr-only"> — {t(`portal.timeline.stateLabel.${step.state}`)}</span>
            </p>
            <p className="portal-timeline-meta">{meta(step)}</p>
          </div>
        </li>
      ))}
    </ol>
  );
}
