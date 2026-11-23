import { useEffect } from "react";

/**
 * Keep <title> and the description in step with the rendered page.
 *
 * Production pages already ship this (plus canonical, hreflang, Open Graph and
 * JSON-LD) in their prerendered <head> — see src/seo.ts — so this mostly
 * matters in the dev server, which serves the bare index.html.
 */
export function useDocumentMeta(title: string, description: string) {
  useEffect(() => {
    document.title = title;
    const meta = document.head.querySelector<HTMLMetaElement>('meta[name="description"]');
    if (meta) meta.content = description;
  }, [title, description]);
}
