// Build-time static site generation (last step of `npm run build`).
//
// `vite build` has produced the client bundle in dist/ and `vite build --ssr`
// the server entry in dist-ssr/. This script renders every language and page
// to HTML, fills dist/index.html's template with it, writes sitemap.xml and
// completes robots.txt, then removes dist-ssr/.
import { mkdir, readFile, rm, writeFile } from "node:fs/promises";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const dist = join(root, "dist");
const ssrDir = join(root, "dist-ssr");

// SITE_URL is VITE_SITE_URL as Vite resolved it (env or .env files), trailing slash removed.
const { SITE_URL: siteUrl, prerenderTargets, renderPage, renderSitemap } = await import(
  pathToFileURL(join(ssrDir, "entry-server.js")).href
);

const HEAD = /<!--app-head-->[\s\S]*?<!--\/app-head-->/;
const ROOT = '<div id="root"></div>';
const HTML_LANG = /<html lang="[^"]*">/;

const template = await readFile(join(dist, "index.html"), "utf8");
if (!HEAD.test(template) || !template.includes(ROOT) || !HTML_LANG.test(template)) {
  throw new Error("dist/index.html is missing the <!--app-head--> markers, the empty #root or <html lang>");
}

for (const target of prerenderTargets()) {
  const { lang, head, html } = renderPage(target);
  if (!html.trim()) throw new Error(`Prerender produced empty markup for ${target.file}`);
  // Function replacements, so `$` sequences in the content are never treated as patterns.
  const page = template
    .replace(HTML_LANG, () => `<html lang="${lang}">`)
    .replace(HEAD, () => head)
    .replace(ROOT, () => `<div id="root">${html}</div>`);
  const file = join(dist, target.file);
  await mkdir(dirname(file), { recursive: true });
  await writeFile(file, page);
  console.log(`prerendered ${target.file}`);
}

await writeFile(join(dist, "sitemap.xml"), renderSitemap());

// robots.txt needs an absolute Sitemap URL, so public/robots.txt holds a placeholder.
const robotsPath = join(dist, "robots.txt");
const robots = await readFile(robotsPath, "utf8");
await writeFile(robotsPath, robots.replaceAll("%SITE_URL%", siteUrl));

await rm(ssrDir, { recursive: true, force: true });
console.log("wrote sitemap.xml and robots.txt");
