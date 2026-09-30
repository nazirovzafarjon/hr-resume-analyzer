import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Vite configuration for the Resume Analyzer landing site.
// Runs on 5174 so it can sit next to the CRM dev server (5173).
// The CRM origin is read from VITE_APP_URL (see .env.example).
export default defineConfig({
  plugins: [react()],
  server: { port: 5174 },
  preview: { port: 4174 },
});
