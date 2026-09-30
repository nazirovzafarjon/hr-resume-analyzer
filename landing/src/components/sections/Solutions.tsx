import { Building2, UserSearch, Users } from "lucide-react";
import SectionHeader from "../ui/SectionHeader";
import { useI18n } from "../../i18n";

const ICONS = [UserSearch, Users, Building2];

export default function Solutions() {
  const { t } = useI18n();
  return (
    <section id="solutions" className="section" aria-labelledby="solutions-title">
      <div className="container">
        <SectionHeader id="solutions-title" eyebrow={t.solutions.eyebrow} title={t.solutions.title} subtitle={t.solutions.subtitle} />
        <ul className="solution-grid">
          {t.solutions.items.map((item, index) => {
            const Icon = ICONS[index];
            return (
              <li key={item.title} className="card solution-card" data-reveal>
                <span className="icon-tile" aria-hidden="true">
                  <Icon size={20} />
                </span>
                <h3>{item.title}</h3>
                <p>{item.text}</p>
              </li>
            );
          })}
        </ul>
      </div>
    </section>
  );
}
