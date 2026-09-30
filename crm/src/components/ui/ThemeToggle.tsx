import { Monitor, Moon, Sun } from "lucide-react";
import Dropdown, { DropdownItem, DropdownLabel } from "./Dropdown";
import { useTheme, type Theme as ThemePreference } from "../../contexts/ThemeContext";
import { useLanguage } from "../../contexts/LanguageContext";
import { translateOr } from "../../utils/statusLabels";

const OPTIONS: { value: ThemePreference; icon: typeof Sun }[] = [
  { value: "light", icon: Sun },
  { value: "dark", icon: Moon },
  { value: "system", icon: Monitor },
];

/**
 * Theme selector (Light / Dark / System). The active preference is marked with
 * `menuitemradio` semantics so screen readers announce the current choice.
 */
export default function ThemeToggle() {
  const { theme, resolvedTheme, setTheme } = useTheme();
  const { t } = useLanguage();

  const ActiveIcon = theme === "dark" ? Moon : theme === "light" ? Sun : Monitor;

  return (
    <Dropdown
      trigger={({ toggle }) => (
        <button
          type="button"
          className="header-icon-button"
          onClick={toggle}
          aria-label={t("appearance.title")}
          title={t("appearance.title")}
        >
          <ActiveIcon size={18} aria-hidden="true" />
        </button>
      )}
    >
      <DropdownLabel>{t("appearance.title")}</DropdownLabel>
      {OPTIONS.map(({ value, icon: Icon }) => (
        <DropdownItem
          key={value}
          role="menuitemradio"
          checked={theme === value}
          icon={<Icon size={16} />}
          onClick={() => setTheme(value)}
          meta={
            theme === "system" && value === "system"
              ? translateOr(t, `theme.${resolvedTheme}`, resolvedTheme)
              : undefined
          }
        >
          {translateOr(t, `theme.${value}`, value)}
        </DropdownItem>
      ))}
    </Dropdown>
  );
}
