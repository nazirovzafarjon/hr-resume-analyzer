import js from "@eslint/js";
import { defineConfig } from "eslint/config";
import globals from "globals";
import reactHooks from "eslint-plugin-react-hooks";
import reactRefresh from "eslint-plugin-react-refresh";
import tseslint from "typescript-eslint";

export default defineConfig(
  { ignores: ["dist", "node_modules"] },
  {
    extends: [js.configs.recommended, ...tseslint.configs.recommended],
    files: ["**/*.{ts,tsx}"],
    languageOptions: {
      ecmaVersion: 2022,
      globals: globals.browser,
    },
    plugins: {
      "react-hooks": reactHooks,
      "react-refresh": reactRefresh,
    },
    rules: {
      ...reactHooks.configs.recommended.rules,
      // react-hooks 7 flags every synchronous setState in an effect body.
      // The existing sites are the common "reset when it opens" and "start
      // loading" patterns: an extra render, not wrong output. Kept visible as
      // warnings so they can be reworked one at a time (see "You Might Not
      // Need an Effect"), instead of a risky rewrite of ~30 effects at once.
      "react-hooks/set-state-in-effect": "warn",
      // A leading underscore marks an intentionally unused parameter.
      "@typescript-eslint/no-unused-vars": [
        "error",
        { argsIgnorePattern: "^_", varsIgnorePattern: "^_", caughtErrorsIgnorePattern: "^_" },
      ],
      "react-refresh/only-export-components": ["warn", { allowConstantExport: true }],
    },
  },
  {
    // Tests capture a hook's result into a variable from a probe component
    // ("let api; function Probe() { api = useX(); }"). That is how hooks are
    // exercised here, not render logic the React Compiler would optimise.
    files: ["**/*.test.{ts,tsx}", "src/test/**/*.{ts,tsx}"],
    rules: {
      "react-hooks/globals": "off",
    },
  },
  {
    // The route table defines lazy page components next to the exported
    // routes. Editing it simply reloads the page; Fast Refresh is not needed.
    files: ["src/routes/index.tsx"],
    rules: {
      "react-refresh/only-export-components": "off",
    },
  },
);
