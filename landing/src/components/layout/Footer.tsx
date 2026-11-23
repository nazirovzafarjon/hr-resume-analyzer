import Logo from "../ui/Logo";
import { useI18n } from "../../i18n";
import { appLinks } from "../../lib/config";

/** Site footer: brand, grouped links and legal line. No social links until real accounts exist. */
export default function Footer() {
  const { t, homeHref, href } = useI18n();
  const groups = [
    {
      title: t.footer.product,
      links: [
        { href: `${homeHref}#features`, label: t.nav.forCompanies },
        { href: `${homeHref}#for-candidates`, label: t.nav.forCandidates },
        { href: appLinks.candidateLogin, label: t.nav.candidatePortal },
        { href: `${homeHref}#how-it-works`, label: t.footer.howItWorks },
        { href: `${homeHref}#analytics`, label: t.footer.analytics },
      ],
    },
    {
      title: t.footer.company,
      links: [
        { href: `${homeHref}#solutions`, label: t.footer.about },
        { href: `${homeHref}#contact`, label: t.footer.contact },
        { href: `${homeHref}#faq`, label: t.footer.faq },
      ],
    },
    {
      title: t.footer.legal,
      links: [
        { href: href("privacy"), label: t.footer.privacy },
        { href: href("terms"), label: t.footer.terms },
      ],
    },
  ];

  return (
    <footer className="footer">
      <div className="container">
        <div className="footer-grid">
          <div className="footer-brand">
            <Logo />
            <p>{t.footer.tagline}</p>
          </div>
          {groups.map((group) => (
            <nav key={group.title} className="footer-group" aria-label={group.title}>
              <h2 className="footer-heading">{group.title}</h2>
              <ul>
                {group.links.map((link) => (
                  <li key={link.href}>
                    <a href={link.href}>{link.label}</a>
                  </li>
                ))}
              </ul>
            </nav>
          ))}
        </div>
        <p className="footer-bottom" suppressHydrationWarning>
          © {new Date().getFullYear()} {t.common.appName}. {t.footer.rights}
        </p>
      </div>
    </footer>
  );
}
