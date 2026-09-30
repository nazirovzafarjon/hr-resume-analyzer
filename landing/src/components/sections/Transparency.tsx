import { Check, Info } from "lucide-react";
import SectionHeader from "../ui/SectionHeader";
import { useI18n } from "../../i18n";

/** The shared promise of both sides: candidates can see where they stand. */
export default function Transparency() {
  const { t } = useI18n();
  return (
    <section id="transparent-hiring" className="section section--alt" aria-labelledby="transparency-title">
      <div className="container">
        <SectionHeader
          id="transparency-title"
          eyebrow={t.transparency.eyebrow}
          title={t.transparency.title}
          subtitle={t.transparency.subtitle}
        />
        <ul className="benefit-grid">
          {t.transparency.items.map((item) => (
            <li key={item.title} className="benefit" data-reveal>
              <span className="benefit-check" aria-hidden="true">
                <Check size={14} strokeWidth={2.5} />
              </span>
              <span>
                <strong>{item.title}</strong>
                <span>{item.text}</span>
              </span>
            </li>
          ))}
        </ul>
        {/* Deliberately modest: the portal shows progress and resume fit, not a
            promise of detailed rejection reasons. */}
        <p className="transparency-note" data-reveal>
          <Info size={16} aria-hidden="true" />
          {t.transparency.note}
        </p>
      </div>
    </section>
  );
}
