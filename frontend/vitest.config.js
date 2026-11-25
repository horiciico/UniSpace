// Vitest (the Vite test runner) for the frontend scripts. Tests run in jsdom, the same DOM the
// pages use. The coverage gate is 100% of lines, branches, functions and statements for every
// browser script: the i18n runtime, the shared components, the session script, and the pages' scripts.
import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    environment: "jsdom",
    include: ["tests/unit/**/*.test.js"],
    setupFiles: ["tests/setup.js"],
    coverage: {
      provider: "v8",
      include: ["i18n/i18n.js", "components/*.js", "js/*.js", "js/pages/*.js"],
      reporter: ["text", "html"],
      thresholds: {
        lines: 100,
        functions: 100,
        branches: 100,
        statements: 100,
      },
    },
  },
});
