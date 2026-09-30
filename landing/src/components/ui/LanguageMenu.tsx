import { Globe } from "lucide-react";
import Menu from "./Menu";
import { LANGUAGES, useI18n, type Language } from "../../i18n";

/** Interface language selector; switching re-renders the page instantly. */
export default function LanguageMenu({ align }: { align?: "start" | "end" }) {
  const { language, setLanguage, t } = useI18n();
  const current = LANGUAGES.find((item) => item.code === language);

  return (
    <Menu<Language>
      label={t.nav.language}
      align={align}
      triggerClassName="icon-button icon-button--text"
      trigger={
        <>
          <Globe size={17} aria-hidden="true" />
          <span aria-hidden="true">{current?.short}</span>
        </>
      }
      value={language}
      onChange={setLanguage}
      options={LANGUAGES.map((item) => ({ value: item.code, label: item.label, meta: item.short }))}
    />
  );
}
