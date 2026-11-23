import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

// Vite configuration for the Resume Analyzer landing site.
// Runs on 5174 so it can sit next to the CRM dev server (5173).
// The CRM origin is read from VITE_APP_URL (see .env.example).
//
// `npm run build` makes two builds — the browser bundle and, with --ssr, the
// server entry that scripts/prerender.mjs uses to write static HTML per
// language — and both need the public site URL for canonical, hreflang,
// Open Graph, JSON-LD and the sitemap.
export default defineConfig(({ command, mode, isSsrBuild }) => {
  if (command === "build") {
    const siteUrl = loadEnv(mode, process.cwd(), "VITE_").VITE_SITE_URL?.trim() ?? "";
    if (!/^https?:\/\/[^/\s]+/.test(siteUrl)) {
      throw new Error(
        "VITE_SITE_URL must be set to the site's public URL (e.g. https://example.com) for production builds. " +
          "It is used for canonical/hreflang links, Open Graph tags and sitemap.xml.",
      );
    }
  }

  return {
    plugins: [react()],
    server: { port: 5174 },
    preview: { port: 4174 },
    // public/ is copied once, by the browser build.
    build: { copyPublicDir: !isSsrBuild },
  };
});
