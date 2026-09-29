import { ChartColumn, ListChecks, Sparkles, Users } from "lucide-react";
import { useI18n } from "../../i18n";

const ICONS = [Sparkles, Users, ListChecks, ChartColumn];

export default function TrustBar() {
  const { t } = useI18n();
  return (
    <section className="trust" aria-label={t.trust.label}>
      <div className="container">
        <ul className="trust-list">
          {t.trust.items.map((item, index) => {
            const Icon = ICONS[index];
            return (
              <li key={item.title} className="trust-item" data-reveal>
                <span className="icon-tile icon-tile--sm" aria-hidden="true">
                  <Icon size={18} />
                </span>
                <span>
                  <strong>{item.title}</strong>
                  <span>{item.text}</span>
                </span>
              </li>
            );
          })}
        </ul>
      </div>
    </section>
  );
}
