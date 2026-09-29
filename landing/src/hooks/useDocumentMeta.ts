import { useEffect } from "react";
import { SITE_URL } from "../lib/config";

function setMeta(selector: string, attribute: "name" | "property", key: string, content: string) {
  let element = document.head.querySelector<HTMLMetaElement>(selector);
  if (!element) {
    element = document.createElement("meta");
    element.setAttribute(attribute, key);
    document.head.appendChild(element);
  }
  element.content = content;
}

/**
 * Keep <title>, the description and Open Graph tags in the active language,
 * and emit a canonical URL when VITE_SITE_URL is configured.
 */
export function useDocumentMeta(title: string, description: string, path = "/") {
  useEffect(() => {
    document.title = title;
    setMeta('meta[name="description"]', "name", "description", description);
    setMeta('meta[property="og:title"]', "property", "og:title", title);
    setMeta('meta[property="og:description"]', "property", "og:description", description);

    if (SITE_URL) {
      const url = `${SITE_URL}${path}`;
      setMeta('meta[property="og:url"]', "property", "og:url", url);
      let canonical = document.head.querySelector<HTMLLinkElement>('link[rel="canonical"]');
      if (!canonical) {
        canonical = document.createElement("link");
        canonical.rel = "canonical";
        document.head.appendChild(canonical);
      }
      canonical.href = url;
    }
  }, [title, description, path]);
}
