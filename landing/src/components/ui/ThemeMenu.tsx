import { Monitor, Moon, Sun } from "lucide-react";
import Menu from "./Menu";
import { useTheme, type ThemePreference } from "../../lib/theme";
import { useI18n } from "../../i18n";

/** Light / Dark / System selector (same three options as the CRM). */
export default function ThemeMenu({ align }: { align?: "start" | "end" }) {
  const { theme, setTheme } = useTheme();
  const { t } = useI18n();
  const ActiveIcon = theme === "dark" ? Moon : theme === "light" ? Sun : Monitor;

  return (
    <Menu<ThemePreference>
      label={t.nav.theme}
      align={align}
      trigger={<ActiveIcon size={18} aria-hidden="true" />}
      value={theme}
      onChange={setTheme}
      options={[
        { value: "light", label: t.nav.themeLight, icon: <Sun size={16} /> },
        { value: "dark", label: t.nav.themeDark, icon: <Moon size={16} /> },
        { value: "system", label: t.nav.themeSystem, icon: <Monitor size={16} /> },
      ]}
    />
  );
}
