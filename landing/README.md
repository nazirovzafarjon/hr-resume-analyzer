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
npm run build                # type-check + production build into dist/
```

| Variable             | Purpose                                                                 |
| -------------------- | ----------------------------------------------------------------------- |
| `VITE_APP_URL`       | CRM origin. Defaults to `http://localhost:5173`.                        |
| `VITE_API_BASE_URL`  | Backend API base for the Contact form. Defaults to `http://localhost:8000/api`. |
| `VITE_SITE_URL`      | Public URL of this site, used for canonical / `og:url`. Optional.       |
| `VITE_CONTACT_EMAIL` | Optional address shown next to the Contact form as a direct `mailto:` link. |

When you deploy, serve `index.html` for `/privacy`, `/terms` and unknown paths
(standard SPA fallback).

## Structure

```text
src/
  i18n/          en.ts (reference) + ru.ts, uz.ts, kiril.ts — typed against en
  lib/           config.ts (env), theme.tsx (light/dark/system), contact.ts (API call)
  hooks/         document meta, section reveal, signed-in hint
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
