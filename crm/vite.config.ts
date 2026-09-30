/// <reference types="vitest/config" />
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Vite configuration for the Resume Analyzer CRM.
// Runs on 5173; the landing site (landing/) runs next to it on 5174.
// The backend API base URL is read from VITE_API_BASE_URL (see .env.example).
export default defineConfig({
  plugins: [react()],
  // Unit/component tests (`npm test`): Vitest reuses this config, so tests
  // compile exactly like the app. jsdom provides the browser APIs.
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    include: ["src/**/*.test.{ts,tsx}"],
    restoreMocks: true,
  },
});
