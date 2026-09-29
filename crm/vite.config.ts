import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Vite configuration for the Resume Analyzer CRM.
// Runs on 5173; the landing site (landing/) runs next to it on 5174.
// The backend API base URL is read from VITE_API_BASE_URL (see .env.example).
export default defineConfig({
  plugins: [react()],
});