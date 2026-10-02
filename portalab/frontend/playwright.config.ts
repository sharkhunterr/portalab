import { defineConfig, devices } from "@playwright/test";

/**
 * Accessibility journeys (spec 022 T020/T021/T039): keyboard-only journey, 320 px reflow, text spacing and
 * axe on the dev component gallery and key routes. The API is stubbed per test (``page.route``), so these
 * run against the Vite dev server only — no backend needed.
 */
export default defineConfig({
  testDir: "tests",
  testMatch: ["a11y/**/*.spec.ts", "e2e/**/*.spec.ts"],
  fullyParallel: true,
  reporter: [["list"]],
  use: { baseURL: "http://127.0.0.1:5199", trace: "retain-on-failure" },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: {
    command: "npx vite --port 5199 --strictPort --host 127.0.0.1",
    url: "http://127.0.0.1:5199",
    reuseExistingServer: !process.env.CI,
    timeout: 60_000,
  },
});
