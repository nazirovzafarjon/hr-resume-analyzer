import { useI18n } from "../../i18n";

/** Brand lockup: the same "RA" mark the CRM uses in its sidebar and auth pages. Links to the home page in the current language. */
export default function Logo() {
  const { t, homeHref } = useI18n();
  return (
    <a className="logo" href={homeHref} aria-label={t.nav.home}>
      <span className="logo-mark" aria-hidden="true">RA</span>
      <span className="logo-name">{t.common.appName}</span>
    </a>
  );
}
