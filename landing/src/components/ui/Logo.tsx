import { useI18n } from "../../i18n";

/** Brand lockup: the same "RA" mark the CRM uses in its sidebar and auth pages. */
export default function Logo({ href = "/" }: { href?: string }) {
  const { t } = useI18n();
  return (
    <a className="logo" href={href} aria-label={t.nav.home}>
      <span className="logo-mark" aria-hidden="true">RA</span>
      <span className="logo-name">{t.common.appName}</span>
    </a>
  );
}
