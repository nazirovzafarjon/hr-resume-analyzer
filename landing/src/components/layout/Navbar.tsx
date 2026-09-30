import { useEffect, useRef, useState } from "react";
import { ArrowRight, Menu as MenuIcon, X } from "lucide-react";
import Logo from "../ui/Logo";
import ThemeMenu from "../ui/ThemeMenu";
import LanguageMenu from "../ui/LanguageMenu";
import { useI18n } from "../../i18n";
import { appLinks } from "../../lib/config";
import { useSignedIn } from "../../hooks/useSignedIn";

const DESKTOP_QUERY = "(min-width: 1024px)";

/**
 * Sticky top navigation. Transparent over the hero, gains a surface and a
 * hairline border once the page scrolls. Below 1024px the links, preferences
 * and CTAs move into a disclosure panel behind the menu button.
 *
 * Visitors with a CRM session see "Open workspace" instead of the log in /
 * sign up pair; the CRM itself re-validates the session on arrival. The
 * "Candidate portal" entry is always there: candidates often arrive through a
 * company's application link and need an obvious way back to their portal.
 */
export default function Navbar() {
  const { t } = useI18n();
  const signedIn = useSignedIn();
  const [scrolled, setScrolled] = useState(false);
  const [open, setOpen] = useState(false);
  const toggleRef = useRef<HTMLButtonElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);

  // Both audiences are visible from the first glance.
  const links = [
    { href: "/#features", label: t.nav.forCompanies },
    { href: "/#for-candidates", label: t.nav.forCandidates },
    { href: "/#how-it-works", label: t.nav.howItWorks },
    { href: "/#faq", label: t.nav.faq },
    { href: "/#contact", label: t.nav.contact },
  ];

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 8);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  // Close the mobile panel when the viewport grows to desktop or on Escape.
  useEffect(() => {
    if (!open) return;
    panelRef.current?.querySelector<HTMLElement>("a, button")?.focus();

    const query = window.matchMedia(DESKTOP_QUERY);
    const onChange = () => query.matches && setOpen(false);
    const onKeyDown = (event: KeyboardEvent) => {
      // A nested menu handles its own Escape first.
      if (event.key === "Escape" && !event.defaultPrevented) {
        setOpen(false);
        toggleRef.current?.focus();
      }
    };
    query.addEventListener("change", onChange);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      query.removeEventListener("change", onChange);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [open]);

  return (
    <header className={`navbar${scrolled || open ? " is-scrolled" : ""}`}>
      <div className="container navbar-inner">
        <Logo />

        <nav className="navbar-links" aria-label={t.nav.label}>
          {links.map((link) => (
            <a key={link.href} href={link.href}>
              {link.label}
            </a>
          ))}
        </nav>

        <div className="navbar-actions">
          <LanguageMenu />
          <ThemeMenu />
          <a className="btn btn--ghost" href={appLinks.candidateLogin}>
            {t.nav.candidatePortal}
          </a>
          {signedIn ? (
            <a className="btn" href={appLinks.workspace}>
              {t.nav.openWorkspace}
              <ArrowRight size={16} aria-hidden="true" />
            </a>
          ) : (
            <>
              <a className="btn btn--ghost" href={appLinks.login}>
                {t.nav.login}
              </a>
              <a className="btn" href={appLinks.register}>
                {t.nav.getStarted}
              </a>
            </>
          )}
        </div>

        <button
          ref={toggleRef}
          type="button"
          className="icon-button navbar-toggle"
          aria-expanded={open}
          aria-controls="mobile-menu"
          aria-label={open ? t.nav.closeMenu : t.nav.openMenu}
          onClick={() => setOpen((current) => !current)}
        >
          {open ? <X size={20} aria-hidden="true" /> : <MenuIcon size={20} aria-hidden="true" />}
        </button>
      </div>

      <div id="mobile-menu" ref={panelRef} className="mobile-menu" hidden={!open}>
        <div className="container">
          <nav aria-label={t.nav.label}>
            <ul className="mobile-menu-links">
              {links.map((link) => (
                <li key={link.href}>
                  <a href={link.href} onClick={() => setOpen(false)}>
                    {link.label}
                  </a>
                </li>
              ))}
            </ul>
          </nav>
          <div className="mobile-menu-prefs">
            <LanguageMenu align="start" />
            <ThemeMenu align="start" />
          </div>
          <div className="mobile-menu-cta">
            <a className="btn btn--secondary btn--lg" href={appLinks.candidateLogin}>
              {t.nav.candidatePortal}
            </a>
            {signedIn ? (
              <a className="btn btn--lg" href={appLinks.workspace}>
                {t.nav.openWorkspace}
                <ArrowRight size={18} aria-hidden="true" />
              </a>
            ) : (
              <>
                <a className="btn btn--secondary btn--lg" href={appLinks.login}>
                  {t.nav.login}
                </a>
                <a className="btn btn--lg" href={appLinks.register}>
                  {t.nav.getStarted}
                </a>
              </>
            )}
          </div>
        </div>
      </div>
    </header>
  );
}
