import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Vite configuration for the Resume Analyzer frontend.
// The backend API base URL is read from VITE_API_BASE_URL (see .env.example).
export default defineConfig({
  plugins: [react()],
});