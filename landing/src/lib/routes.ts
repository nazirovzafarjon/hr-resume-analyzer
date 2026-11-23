/**
 * URL scheme of the site. Pure functions (no DOM), shared by the browser
 * bundle and the build-time prerender (src/entry-server.tsx).
 *
 * Every language has its own URL so search engines and link previews see
 * localized markup: Uzbek (the primary market, and copy-complete) lives at the
 * root and is the `x-default`; the others sit under a path prefix.
 *
 *   /            /privacy        /terms          (uz, x-default)
 *   /ru/         /ru/privacy     /ru/terms
 *   /en/         /en/privacy     /en/terms
 *   /uz-cyrl/    /uz-cyrl/privacy /uz-cyrl/terms
 */

/** Same language codes as the CRM (crm/src/contexts/LanguageContext.tsx). */
export type Language = "uz" | "en" | "ru" | "kiril";

export type Page = "home" | "privacy" | "terms" | "notFound";

export const DEFAULT_LANGUAGE: Language = "uz";

/** Order used by the language menu, hreflang alternates and the sitemap. */
export const LANGUAGE_CODES: Language[] = ["uz", "kiril", "ru", "en"];

/** Path prefix of each language ("" = site root). */
export const LANGUAGE_PREFIX: Record<Language, string> = {
  uz: "",
  kiril: "/uz-cyrl",
  ru: "/ru",
  en: "/en",
};

/** BCP 47 tag for `<html lang>` and `hreflang`. */
export const HTML_LANG: Record<Language, string> = { uz: "uz", kiril: "uz-Cyrl", ru: "ru", en: "en" };

/** Open Graph locale (language_TERRITORY). */
export const OG_LOCALE: Record<Language, string> = { uz: "uz_UZ", kiril: "uz_UZ", ru: "ru_RU", en: "en_US" };

const PAGE_PATH: Record<Exclude<Page, "notFound">, string> = {
  home: "/",
  privacy: "/privacy",
  terms: "/terms",
};

/** Pages listed in the sitemap and open to indexing. The legal pages join once they hold real documents. */
export const INDEXABLE_PAGES: Page[] = ["home"];

/** Language and page for a pathname; the language always comes from the URL. */
export function parsePath(pathname: string): { language: Language; page: Page } {
  let rest = pathname.replace(/\/+$/, "") || "/";
  let language: Language = DEFAULT_LANGUAGE;

  for (const code of LANGUAGE_CODES) {
    const prefix = LANGUAGE_PREFIX[code];
    if (prefix && (rest === prefix || rest.startsWith(`${prefix}/`))) {
      language = code;
      rest = rest.slice(prefix.length) || "/";
      break;
    }
  }

  const page = (Object.keys(PAGE_PATH) as (keyof typeof PAGE_PATH)[]).find((key) => PAGE_PATH[key] === rest);
  return { language, page: page ?? "notFound" };
}

/** Site-relative URL of a page in a language, e.g. "/ru/" or "/ru/privacy". */
export function pagePath(language: Language, page: Exclude<Page, "notFound">): string {
  const prefix = LANGUAGE_PREFIX[language];
  return page === "home" ? `${prefix}/` : `${prefix}${PAGE_PATH[page]}`;
}
