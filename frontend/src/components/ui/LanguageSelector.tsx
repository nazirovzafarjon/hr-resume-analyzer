import { Globe } from "lucide-react";
import Dropdown, { DropdownItem, DropdownLabel } from "./Dropdown";
import { useLanguage, LANGUAGE_LABELS, type Language } from "../../contexts/LanguageContext";

const LANGUAGES: Language[] = ["uz", "en", "ru", "kiril"];

const LANGUAGE_CODES: Record<Language, string> = {
  uz: "UZB",
  en: "ENG",
  ru: "RUS",
  kiril: "KIRIL",
};

/**
 * Interface language selector. Switching re-renders the whole UI immediately —
 * no reload — and the choice is persisted by the language provider.
 */
export default function LanguageSelector({ compact = false }: { compact?: boolean }) {
  const { language, setLanguage } = useLanguage();

  return (
    <Dropdown
      trigger={({ toggle }) => (
        <button
          type="button"
          className="language-selector-trigger"
          onClick={toggle}
          aria-label="Select language"
          title={`Language: ${LANGUAGE_LABELS[language]}`}
        >
          <Globe size={17} aria-hidden="true" />
          {!compact && <span>{LANGUAGE_LABELS[language]}</span>}
          <span className="language-selector-code">{LANGUAGE_CODES[language]}</span>
        </button>
      )}
    >
      <DropdownLabel>Language</DropdownLabel>
      {LANGUAGES.map((code) => (
        <DropdownItem
          key={code}
          role="menuitemradio"
          checked={language === code}
          onClick={() => setLanguage(code)}
          meta={LANGUAGE_CODES[code]}
        >
          {LANGUAGE_LABELS[code]}
        </DropdownItem>
      ))}
    </Dropdown>
  );
}
