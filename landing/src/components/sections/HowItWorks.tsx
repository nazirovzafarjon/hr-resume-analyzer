import SectionHeader from "../ui/SectionHeader";
import { useI18n } from "../../i18n";

export default function HowItWorks() {
  const { t } = useI18n();
  return (
    <section id="how-it-works" className="section section--alt" aria-labelledby="how-title">
      <div className="container">
        <SectionHeader id="how-title" eyebrow={t.how.eyebrow} title={t.how.title} subtitle={t.how.subtitle} />
        <ol className="steps">
          {t.how.steps.map((step, index) => (
            <li key={step.title} className="step" data-reveal>
              <span className="step-number" aria-hidden="true">
                {String(index + 1).padStart(2, "0")}
              </span>
              <h3>{step.title}</h3>
              <p>{step.text}</p>
            </li>
          ))}
        </ol>
      </div>
    </section>
  );
}
