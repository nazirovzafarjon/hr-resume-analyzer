# Resume Analyzer — Landing site

The public marketing site for Resume Analyzer. It is a separate Vite + React +
TypeScript app next to the CRM (`crm/`) and the API (`backend/`).

```text
backend/    FastAPI API
crm/        HR CRM (auth pages, dashboard, jobs, candidates, …)
landing/    this site
```

## How it connects to the product

**Log in** and **Get started** link to the CRM's existing `/login` and
`/register` pages (`VITE_APP_URL`), which already handle email/password, Google
sign-in, password reset, error messages and the JWT session. There is no second
auth system.

- **Signed-in visitors.** The CRM keeps its tokens in its own `localStorage`,
  which this site cannot read. Instead the CRM sets a non-secret
  `resumeAnalyzer.signedIn=1` cookie while a session exists (and clears it on
  logout). When it is present the navbar shows **Open workspace**
  (`<VITE_APP_URL>/dashboard`); the CRM still validates and refreshes the real
  session there. Cookies ignore the port, so this works for the two dev servers
  as-is; in production put both apps on one host or on sibling subdomains with
  the CRM's `VITE_SESSION_COOKIE_DOMAIN` set to the parent domain.
- **Contact form.** The only backend call: `POST /api/public/contact` (no
  account needed). The backend's `BACKEND_CORS_ORIGINS` must list this site.

Every other section is static. Numbers in the product illustrations are sample
data and are labelled that way on the page.

## Run it

```bash
cd landing
cp .env.example .env.local   # adjust VITE_APP_URL if the CRM is not on :5173
npm install
npm run dev                  # http://localhost:5174
VITE_SITE_URL=https://example.com npm run build   # type-check, build, prerender into dist/
```

| Variable             | Purpose                                                                 |
| -------------------- | ----------------------------------------------------------------------- |
| `VITE_APP_URL`       | CRM origin. Defaults to `http://localhost:5173`.                        |
| `VITE_API_BASE_URL`  | Backend API base for the Contact form. Defaults to `http://localhost:8000/api`. |
| `VITE_SITE_URL`      | Public URL of this site (e.g. `https://example.com`). **Required for `npm run build`**: canonical, hreflang, Open Graph, JSON-LD, `sitemap.xml` and `robots.txt` are generated from it. Not needed for `npm run dev`. |
| `VITE_CONTACT_EMAIL` | Optional address shown next to the Contact form as a direct `mailto:` link. |

## Languages, URLs and prerendering

Every language has its own URL, and the language always comes from the path
(`src/lib/routes.ts`):

| Language          | Home        | Legal pages                              |
| ----------------- | ----------- | ---------------------------------------- |
| O'zbekcha (`uz`)  | `/`         | `/privacy`, `/terms`                     |
| Ўзбекча (`kiril`) | `/uz-cyrl/` | `/uz-cyrl/privacy`, `/uz-cyrl/terms`     |
| Русский (`ru`)    | `/ru/`      | `/ru/privacy`, `/ru/terms`               |
| English (`en`)    | `/en/`      | `/en/privacy`, `/en/terms`               |

Uzbek sits at the root and is the `x-default`: it is the primary market and its
copy is complete. The language menu navigates between these URLs and stores
the choice (same key as the CRM); a visitor with a stored choice who lands on an
unprefixed page is redirected to their language by the inline script in
`index.html`. The browser locale never redirects, so crawlers always get the
page at the URL they requested.

`npm run build` runs `vite build`, then `vite build --ssr src/entry-server.tsx`
and `scripts/prerender.mjs`, which renders every page with `renderToString`
into `dist/` (`index.html`, `ru/index.html`, `privacy.html`, `ru/privacy.html`,
one `404.html` per language, …) with its localized `<title>`, description,
canonical, `hreflang` alternates, Open Graph/Twitter tags and, on home pages,
JSON-LD (`Organization`, `SoftwareApplication`, `FAQPage` from `t.faq.items`).
It also writes `sitemap.xml` and fills the `Sitemap:` line of `robots.txt`.
The browser hydrates that markup (`hydrateRoot` in `src/main.tsx`), so initial
render must not read browser-only state — theme and signed-in hint are read in
effects after hydration.

The legal pages are `noindex` and left out of the sitemap while they are
placeholders; add them to `INDEXABLE_PAGES` in `src/lib/routes.ts` once real
documents are published.

`nginx.conf` serves those files at their clean URLs, returns a real `404`
(with the language's prerendered 404 page) for unknown paths, and sets cache
headers per file type; `security-headers.conf` is included in every location
because nginx does not inherit `add_header` into a location that sets its own.
In Docker, pass the `VITE_*` values as build args (see `Dockerfile` and
`docker-compose.prod.yml`).

## Structure

```text
src/
  i18n/          en.ts (reference) + ru.ts, uz.ts, kiril.ts — typed against en
  lib/           config.ts (env), theme.tsx (light/dark/system), contact.ts (API call)
  hooks/         document meta, section reveal, signed-in hint
  lib/routes.ts  language/page <-> URL mapping
  seo.ts         prerendered <head> (meta, hreflang, JSON-LD) and sitemap.xml
  entry-server.tsx  build-time render entry used by scripts/prerender.mjs
  components/
    layout/      Navbar, Footer
    sections/    Hero, TrustBar, Features, HowItWorks, Workflow, ResumeAnalysis,
                 Solutions, Benefits, AnalyticsPreview, Security, Faq, Contact, FinalCta
    visuals/     DashboardMockup, AnalysisCard, AnalyticsCard, BarSparkline
    ui/          Logo, Menu, LanguageMenu, ThemeMenu, SectionHeader
  pages/         LandingPage, SimplePage (legal placeholders, 404)
  styles/        tokens.css (copied from the CRM), base.css, landing.css
```

- **Design tokens.** `styles/tokens.css` is a copy of the token sections of
  `crm/src/index.css`. It is copied rather than imported so the two apps
  deploy independently. Keep them in sync when the CRM palette changes.
- **Preferences.** The theme and language use the same `localStorage` keys and
  values as the CRM (`resume-analyzer-theme`, `resume-analyzer-language`). If both
  apps are served from one origin, the visitor's choice carries over.
- **Translations.** Adding a key to `en.ts` fails the build until every other
  language has it too.
