type SectionHeaderProps = {
  id: string;
  eyebrow: string;
  title: string;
  subtitle?: string;
  align?: "center" | "start";
};

/** Eyebrow + h2 + lead paragraph used at the top of every landing section. */
export default function SectionHeader({ id, eyebrow, title, subtitle, align = "center" }: SectionHeaderProps) {
  return (
    <header className={`section-header section-header--${align}`} data-reveal>
      <p className="eyebrow">{eyebrow}</p>
      <h2 id={id} className="section-title">{title}</h2>
      {subtitle && <p className="section-subtitle">{subtitle}</p>}
    </header>
  );
}
