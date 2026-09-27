const SITE_NAME = "Resume Analyzer";

type OpenGraph = {
  title?: string;
  description?: string;
  type?: string;
};

type PageMetaProps = {
  /** Page-specific title; the site name is appended automatically. */
  title: string;
  description?: string;
  /** Protected/HR-only pages must opt in so private data is never indexed. */
  noindex?: boolean;
  /** Present only on pages meant to be shared/previewed (e.g. the public apply page). */
  og?: OpenGraph;
  twitterCard?: "summary" | "summary_large_image";
};

/**
 * Per-page document metadata. React 19 hoists `<title>`/`<meta>` rendered
 * anywhere in the tree into `<head>` automatically (de-duplicated, and
 * removed again on unmount) — no head-management dependency needed.
 */
export default function PageMeta({ title, description, noindex, og, twitterCard }: PageMetaProps) {
  const fullTitle = `${title} — ${SITE_NAME}`;
  const ogDescription = og?.description ?? description;

  return (
    <>
      <title>{fullTitle}</title>
      {description && <meta name="description" content={description} />}
      <meta name="robots" content={noindex ? "noindex, nofollow" : "index, follow"} />
      {og && (
        <>
          <meta property="og:site_name" content={SITE_NAME} />
          <meta property="og:type" content={og.type ?? "website"} />
          <meta property="og:title" content={og.title ?? fullTitle} />
          {ogDescription && <meta property="og:description" content={ogDescription} />}
          <meta name="twitter:card" content={twitterCard ?? "summary"} />
          <meta name="twitter:title" content={og.title ?? fullTitle} />
          {ogDescription && <meta name="twitter:description" content={ogDescription} />}
        </>
      )}
    </>
  );
}
