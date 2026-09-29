import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
// Design-system primitives first, so page/feature stylesheets (imported by
// the components below) build on them rather than being overridden by them.
import "./index.css";
import App from "./App";

const rootElement = document.getElementById("root");
if (!rootElement) {
  throw new Error("Root element #root not found");
}

createRoot(rootElement).render(
  <StrictMode>
    <App />
  </StrictMode>
);

