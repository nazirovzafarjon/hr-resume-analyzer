import { useState } from "react";
import { ChevronDown } from "lucide-react";
import SectionHeader from "../ui/SectionHeader";
import { useI18n } from "../../i18n";

/** Accordion (disclosure buttons + labelled regions); several items can be open at once. */
export default function Faq() {
  const { t } = useI18n();
  const [openItems, setOpenItems] = useState<Set<number>>(() => new Set([0]));

  function toggle(index: number) {
    setOpenItems((current) => {
      const next = new Set(current);
      if (next.has(index)) next.delete(index);
      else next.add(index);
      return next;
    });
  }

  return (
    <section id="faq" className="section" aria-labelledby="faq-title">
      <div className="container faq-layout">
        <SectionHeader id="faq-title" eyebrow={t.faq.eyebrow} title={t.faq.title} subtitle={t.faq.subtitle} align="start" />
        <div className="faq-list" data-reveal>
          {t.faq.items.map((item, index) => {
            const open = openItems.has(index);
            const buttonId = `faq-q-${index}`;
            const panelId = `faq-a-${index}`;
            return (
              <div key={index} className={`faq-item${open ? " is-open" : ""}`}>
                <h3>
                  <button
                    id={buttonId}
                    type="button"
                    className="faq-question"
                    aria-expanded={open}
                    aria-controls={panelId}
                    onClick={() => toggle(index)}
                  >
                    <span>{item.q}</span>
                    <ChevronDown size={18} aria-hidden="true" />
                  </button>
                </h3>
                <div id={panelId} role="region" aria-labelledby={buttonId} className="faq-answer" hidden={!open}>
                  <p>{item.a}</p>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
}
