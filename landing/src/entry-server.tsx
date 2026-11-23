/**
 * Server entry used only at build time: `vite build --ssr` bundles this file
 * and scripts/prerender.mjs calls it to write one static HTML file per
 * language and page. The browser then hydrates that markup (src/main.tsx).
 */
import { StrictMode } from "react";
import { renderToString } from "react-dom/server";
import App from "./App";
import { I18nProvider } from "./i18n";
import { ThemeProvider } from "./lib/theme";
import { HTML_LANG, LANGUAGE_CODES, LANGUAGE_PREFIX, type Language, type Page } from "./lib/routes";
import { renderHead, renderSitemap } from "./seo";

export type PrerenderTarget = {
  language: Language;
  page: Page;
  /** Output path inside dist/, e.g. "ru/index.html" or "ru/privacy.html". */
  file: string;
};

const FILE_NAME: Record<Page, string> = {
  home: "index.html",
  privacy: "privacy.html",
  terms: "terms.html",
  notFound: "404.html",
};

/**
 * Every file to write. nginx serves `/ru/privacy` from `ru/privacy.html`
 * (`try_files $uri $uri.html $uri/`) and each language's `404.html` with a real
 * 404 status for unknown paths under its prefix.
 */
export function prerenderTargets(): PrerenderTarget[] {
  return LANGUAGE_CODES.flatMap((language) => {
    const dir = LANGUAGE_PREFIX[language].replace(/^\//, "");
    return (Object.keys(FILE_NAME) as Page[]).map((page) => ({
      language,
      page,
      file: dir ? `${dir}/${FILE_NAME[page]}` : FILE_NAME[page],
    }));
  });
}

export function renderPage({ language, page }: PrerenderTarget): { lang: string; head: string; html: string } {
  const html = renderToString(
    <StrictMode>
      <ThemeProvider>
        <I18nProvider language={language} page={page}>
          <App />
        </I18nProvider>
      </ThemeProvider>
    </StrictMode>,
  );
  return { lang: HTML_LANG[language], head: renderHead(language, page), html };
}

export { renderSitemap };
export { SITE_URL } from "./lib/config";
