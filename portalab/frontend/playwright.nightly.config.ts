import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { defineConfig, devices } from "@playwright/test";

/**
 * Issue 469 — the nightly regression suite: the real portal (fresh database, demo data, every shop product
 * given to its Admin — backend/tests/nightly/nightly.sh) with the production bundle, and the matrix of what
 * the shop sells — every interface, widget and option, every statistic — on a phone, a tablet and a desktop.
 * Each page is checked for what a member sees: it renders without a crash, fits the screen, stays readable
 * (axe with contrast, no clipped label) and smooth (long tasks, frames under a slowed processor).
 */
const OUT = process.env.NIGHTLY_OUT ?? resolve("nightly-report");
const state = process.env.NIGHTLY_STATE
  ? (JSON.parse(readFileSync(process.env.NIGHTLY_STATE, "utf8")) as { base: string })
  : { base: "http://127.0.0.1:8098" };

export default defineConfig({
  testDir: "tests/nightly",
  testMatch: ["**/*.spec.ts"],
  globalSetup: "./tests/nightly/global-setup.ts",
  fullyParallel: true,
  workers: Number(process.env.NIGHTLY_WORKERS ?? 2),
  // a failure is told the next morning rather than played again (the matrix is long); NIGHTLY_RETRIES=1 tells a
  // hiccup of the shared runner from a regression
  retries: Number(process.env.NIGHTLY_RETRIES ?? 0),
  timeout: 180_000,
  expect: { timeout: 15_000 },
  outputDir: resolve(OUT, "results"),
  reporter: [
    ["list"],
    ["junit", { outputFile: resolve(OUT, "junit.xml") }],
    ["html", { outputFolder: resolve(OUT, "html"), open: "never" }],
    ["./tests/nightly/summary-reporter.ts", { outputFile: resolve(OUT, "summary.md") }],
  ],
  use: {
    baseURL: state.base,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    locale: "en-US",
    timezoneId: "Europe/Paris",
  },
  projects: [
    {
      name: "phone",
      use: { ...devices["Desktop Chrome"], viewport: { width: 390, height: 844 }, hasTouch: true },
    },
    {
      name: "tablet",
      use: { ...devices["Desktop Chrome"], viewport: { width: 820, height: 1180 }, hasTouch: true },
    },
    { name: "desktop", use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 900 } } },
  ],
});
