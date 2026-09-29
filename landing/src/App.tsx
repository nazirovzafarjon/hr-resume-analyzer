import Navbar from "./components/layout/Navbar";
import Footer from "./components/layout/Footer";
import LandingPage from "./pages/LandingPage";
import SimplePage from "./pages/SimplePage";
import { useI18n } from "./i18n";

/**
 * The site has one real page plus two legal placeholders, so a router
 * dependency isn't worth it: the path is read once and links are plain
 * anchors. Log in / Get started leave for the CRM's own auth pages.
 */
function Page() {
  const { t } = useI18n();
  const path = window.location.pathname.replace(/\/+$/, "") || "/";

  switch (path) {
    case "/":
      return <LandingPage />;
    case "/privacy":
      return <SimplePage path={path} title={t.legal.privacyTitle} text={t.legal.placeholder} back={t.legal.back} />;
    case "/terms":
      return <SimplePage path={path} title={t.legal.termsTitle} text={t.legal.placeholder} back={t.legal.back} />;
    default:
      return <SimplePage path={path} title={t.notFound.title} text={t.notFound.text} back={t.notFound.back} />;
  }
}

export default function App() {
  const { t } = useI18n();
  return (
    <>
      <a className="skip-link" href="#main">
        {t.common.skipToContent}
      </a>
      <Navbar />
      <main id="main" tabIndex={-1}>
        <Page />
      </main>
      <Footer />
    </>
  );
}
