import { Check } from "lucide-react";
import SectionHeader from "../ui/SectionHeader";
import { useI18n } from "../../i18n";

export default function Benefits() {
  const { t } = useI18n();
  return (
    <section id="benefits" className="section section--alt" aria-labelledby="benefits-title">
      <div className="container">
        <SectionHeader id="benefits-title" eyebrow={t.benefits.eyebrow} title={t.benefits.title} />
        <ul className="benefit-grid">
          {t.benefits.items.map((item) => (
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
      </div>
    </section>
  );
}
