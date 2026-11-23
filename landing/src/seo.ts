/**
 * Build-time SEO: the localized <head> of every prerendered page and the
 * sitemap. Only imported by src/entry-server.tsx, never by the browser bundle.
 */
import { DICTIONARIES } from "./i18n";
import type { Dictionary } from "./i18n/en";
import { SITE_URL } from "./lib/config";
import {
  DEFAULT_LANGUAGE,
  HTML_LANG,
  INDEXABLE_PAGES,
  LANGUAGE_CODES,
  OG_LOCALE,
  pagePath,
  type Language,
  type Page,
} from "./lib/routes";

/** 1200×630 share image in public/. */
const OG_IMAGE = { path: "/og-image.png", width: 1200, height: 630 };

function escapeHtml(value: string): string {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

/** JSON for an inline <script>; `<` is escaped so the text can never close the tag. */
function jsonLd(data: unknown): string {
  const json = JSON.stringify(data).replace(/</g, "\\u003c");
  return `<script type="application/ld+json">${json}</script>`;
}

function absolute(path: string): string {
  if (!SITE_URL) throw new Error("VITE_SITE_URL is required to prerender the site");
  return `${SITE_URL}${path}`;
}

export function pageTitle(t: Dictionary, page: Page): string {
  switch (page) {
    case "home":
      return t.meta.title;
    case "privacy":
      return `${t.legal.privacyTitle} — ${t.common.appName}`;
    case "terms":
      return `${t.legal.termsTitle} — ${t.common.appName}`;
    case "notFound":
      return `${t.notFound.title} — ${t.common.appName}`;
  }
}

function pageDescription(t: Dictionary, page: Page): string {
  switch (page) {
    case "home":
      return t.meta.description;
    case "privacy":
    case "terms":
      return t.legal.placeholder;
    case "notFound":
      return t.notFound.text;
  }
}

function structuredData(language: Language, t: Dictionary): string[] {
  const home = absolute(pagePath(language, "home"));
  const organization = {
    "@context": "https://schema.org",
    "@type": "Organization",
    "@id": `${absolute("/")}#organization`,
    name: t.common.appName,
    url: absolute("/"),
    logo: absolute("/icon-512.png"),
  };
  const application = {
    "@context": "https://schema.org",
    "@type": "SoftwareApplication",
    name: t.common.appName,
    url: home,
    description: t.meta.description,
    inLanguage: HTML_LANG[language],
    applicationCategory: "BusinessApplication",
    operatingSystem: "Web",
    image: absolute(OG_IMAGE.path),
    publisher: { "@id": organization["@id"] },
  };
  const faq = {
    "@context": "https://schema.org",
    "@type": "FAQPage",
    inLanguage: HTML_LANG[language],
    mainEntity: t.faq.items.map((item) => ({
      "@type": "Question",
      name: item.q,
      acceptedAnswer: { "@type": "Answer", text: item.a },
    })),
  };
  return [jsonLd(organization), jsonLd(application), jsonLd(faq)];
}

/** Everything that goes between the `<!--app-head-->` markers of index.html. */
export function renderHead(language: Language, page: Page): string {
  const t = DICTIONARIES[language];
  const title = pageTitle(t, page);
  const description = pageDescription(t, page);
  const image = absolute(OG_IMAGE.path);

  const tags = [
    `<title>${escapeHtml(title)}</title>`,
    `<meta name="description" content="${escapeHtml(description)}" />`,
  ];

  if (page === "notFound") {
    tags.push(`<meta name="robots" content="noindex" />`);
  } else {
    const url = absolute(pagePath(language, page));
    if (!INDEXABLE_PAGES.includes(page)) tags.push(`<meta name="robots" content="noindex, follow" />`);
    tags.push(`<link rel="canonical" href="${escapeHtml(url)}" />`);
    for (const code of LANGUAGE_CODES) {
      tags.push(
        `<link rel="alternate" hreflang="${HTML_LANG[code]}" href="${escapeHtml(absolute(pagePath(code, page)))}" />`,
      );
    }
    tags.push(
      `<link rel="alternate" hreflang="x-default" href="${escapeHtml(absolute(pagePath(DEFAULT_LANGUAGE, page)))}" />`,
      `<meta property="og:url" content="${escapeHtml(url)}" />`,
    );
  }

  tags.push(
    `<meta property="og:type" content="website" />`,
    `<meta property="og:site_name" content="${escapeHtml(t.common.appName)}" />`,
    `<meta property="og:title" content="${escapeHtml(title)}" />`,
    `<meta property="og:description" content="${escapeHtml(description)}" />`,
    `<meta property="og:locale" content="${OG_LOCALE[language]}" />`,
    ...[...new Set(LANGUAGE_CODES.map((code) => OG_LOCALE[code]))]
      .filter((locale) => locale !== OG_LOCALE[language])
      .map((locale) => `<meta property="og:locale:alternate" content="${locale}" />`),
    `<meta property="og:image" content="${escapeHtml(image)}" />`,
    `<meta property="og:image:type" content="image/png" />`,
    `<meta property="og:image:width" content="${OG_IMAGE.width}" />`,
    `<meta property="og:image:height" content="${OG_IMAGE.height}" />`,
    `<meta property="og:image:alt" content="${escapeHtml(t.common.appName)}" />`,
    `<meta name="twitter:card" content="summary_large_image" />`,
    `<meta name="twitter:title" content="${escapeHtml(title)}" />`,
    `<meta name="twitter:description" content="${escapeHtml(description)}" />`,
    `<meta name="twitter:image" content="${escapeHtml(image)}" />`,
  );

  if (page === "home") tags.push(...structuredData(language, t));

  return tags.join("\n    ");
}

/** sitemap.xml with every indexable page and its language alternates. */
export function renderSitemap(): string {
  const entries = INDEXABLE_PAGES.flatMap((page) => {
    if (page === "notFound") return [];
    const alternates = [
      ...LANGUAGE_CODES.map(
        (code) =>
          `    <xhtml:link rel="alternate" hreflang="${HTML_LANG[code]}" href="${escapeHtml(absolute(pagePath(code, page)))}" />`,
      ),
      `    <xhtml:link rel="alternate" hreflang="x-default" href="${escapeHtml(absolute(pagePath(DEFAULT_LANGUAGE, page)))}" />`,
    ].join("\n");
    return LANGUAGE_CODES.map(
      (code) => `  <url>\n    <loc>${escapeHtml(absolute(pagePath(code, page)))}</loc>\n${alternates}\n  </url>`,
    );
  });

  return [
    `<?xml version="1.0" encoding="UTF-8"?>`,
    `<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xhtml="http://www.w3.org/1999/xhtml">`,
    ...entries,
    `</urlset>`,
    ``,
  ].join("\n");
}
