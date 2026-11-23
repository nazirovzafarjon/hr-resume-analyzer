import { StrictMode } from "react";
import { createRoot, hydrateRoot } from "react-dom/client";
import App from "./App";
import { I18nProvider } from "./i18n";
import { ThemeProvider } from "./lib/theme";
import { parsePath } from "./lib/routes";
import "./styles/tokens.css";
import "./styles/base.css";
import "./styles/landing.css";

const rootElement = document.getElementById("root");
if (!rootElement) throw new Error("Root element #root not found");

const { language, page } = parsePath(window.location.pathname);

const app = (
  <StrictMode>
    <ThemeProvider>
      <I18nProvider language={language} page={page}>
        <App />
      </I18nProvider>
    </ThemeProvider>
  </StrictMode>
);

// Production pages are prerendered at build time (scripts/prerender.mjs), so
// React attaches to the existing markup; the dev server ships an empty root.
if (rootElement.hasChildNodes()) hydrateRoot(rootElement, app);
else createRoot(rootElement).render(app);
