import { Briefcase, ChartColumn, FileSearch, Link2, ListChecks, Users } from "lucide-react";
import SectionHeader from "../ui/SectionHeader";
import { useI18n } from "../../i18n";

const ICONS = [FileSearch, Briefcase, Link2, Users, ListChecks, ChartColumn];

export default function Features() {
  const { t } = useI18n();
  return (
    <section id="features" className="section" aria-labelledby="features-title">
      <div className="container">
        <SectionHeader id="features-title" eyebrow={t.features.eyebrow} title={t.features.title} subtitle={t.features.subtitle} />
        <ul className="feature-grid">
          {t.features.items.map((item, index) => {
            const Icon = ICONS[index];
            return (
              <li key={item.title} className="card feature-card" data-reveal>
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
