import { Hash, KeyRound, Lock, ShieldCheck, UserCheck } from "lucide-react";
import SectionHeader from "../ui/SectionHeader";
import { useI18n } from "../../i18n";

const ICONS = [Lock, KeyRound, Hash, ShieldCheck, UserCheck];

export default function Security() {
  const { t } = useI18n();
  return (
    <section id="security" className="section section--alt" aria-labelledby="security-title">
      <div className="container">
        <SectionHeader id="security-title" eyebrow={t.security.eyebrow} title={t.security.title} subtitle={t.security.subtitle} />
        <ul className="security-grid">
          {t.security.items.map((item, index) => {
            const Icon = ICONS[index];
            return (
              <li key={item.title} className="security-item" data-reveal>
                <Icon size={20} aria-hidden="true" />
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
