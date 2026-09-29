import { BadgeCheck, Briefcase, CalendarClock, FileText, Hand, Sparkles, UserCheck } from "lucide-react";
import SectionHeader from "../ui/SectionHeader";
import { useI18n } from "../../i18n";

const ICONS = [Briefcase, FileText, Sparkles, UserCheck, CalendarClock, BadgeCheck];

export default function Workflow() {
  const { t } = useI18n();
  const last = t.workflow.stages.length - 1;
  return (
    <section id="workflow" className="section" aria-labelledby="workflow-title">
      <div className="container">
        <SectionHeader id="workflow-title" eyebrow={t.workflow.eyebrow} title={t.workflow.title} subtitle={t.workflow.subtitle} />
        <ol className="workflow" data-reveal>
          {t.workflow.stages.map((stage, index) => {
            const Icon = ICONS[index];
            return (
              <li key={stage.title} className={`workflow-stage${index === last ? " is-decision" : ""}`}>
                <span className="workflow-icon" aria-hidden="true">
                  <Icon size={18} />
                </span>
                <span className="workflow-text">
                  <strong>{stage.title}</strong>
                  <span>{stage.text}</span>
                </span>
              </li>
            );
          })}
        </ol>
        <p className="workflow-note" data-reveal>
          <Hand size={18} aria-hidden="true" />
          {t.workflow.note}
        </p>
      </div>
    </section>
  );
}
