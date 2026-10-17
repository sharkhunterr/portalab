import { expect, type Page, test } from "@playwright/test";
import { stubApi } from "../../a11y/support";
import { element, packFile, servePack } from "./support";

// 029 — safe mode: from an address with ``?safe=1`` Portalab's own interface is shown, nothing of a pack
// is asked for (no active elements, no file, no sandbox) and its banner says so; leaving it reloads the
// page with the member's interface and its navigation back.

const INTERFACE = element("abysses", "interface-abysses", {
  product: "theme_abysses",
  type: "theme",
  look: "abysses",
  kind: "theme",
  file: "interface.json",
  css: ["interface.css"],
  names: { en: "Abysses interface" },
});
const SONAR = element("abysses", "nav-sonar", {
  product: "nav_sonar",
  type: "navigation",
  look: "sonar",
  kind: "js",
  file: "sonar.js",
  nav: { position: "bottom", size: 76, expands: true },
  names: { en: "Sonar" },
});

async function signIn(page: Page, address: string) {
  await page.setViewportSize({ width: 1280, height: 900 });
  await stubApi(page);
  await servePack(page, "abysses");
  await page.route("**/api/v1/me/preferences", (route) =>
    route.fulfill({ json: { preferences: [{ key: "ui.theme", value: "abysses" }] } }),
  );
  await page.route("**/api/v1/ui/themes", (route) =>
    route.fulfill({
      json: {
        themes: [
          { key: "abysses", definition: JSON.parse(packFile("abysses", "interface-abysses/interface.json")) },
        ],
        policy: {
          allowedThemes: ["light", "dark", "high-contrast", "abysses"],
          defaultTheme: "light",
          textScaleMin: 0.85,
          textScaleMax: 2,
          forceReducedMotion: false,
        },
      },
    }),
  );
  await page.route("**/api/v1/visuals/active", (route) =>
    route.fulfill({ json: { epoch: 1, withheld: {}, elements: [INTERFACE, SONAR] } }),
  );
  await page.goto(address);
  await page.getByLabel(/login/i).first().fill("alex");
  await page
    .getByLabel(/password/i)
    .first()
    .fill("correct horse battery");
  await page.keyboard.press("Enter");
  await expect(page.locator("#main-content")).toBeVisible();
}

test("safe mode from the address asks for nothing of a pack, and its banner leaves it", async ({ page }) => {
  const asked: string[] = [];
  page.on("request", (request) => {
    if (/\/api\/v1\/visuals\/(active|files|sandbox|live)/.test(request.url())) asked.push(request.url());
  });
  await signIn(page, "/?safe=1");
  const banner = page.locator("[data-safe='true']");
  await expect(banner).toBeVisible();
  await expect(page).not.toHaveURL(/safe=/); // the address keeps no trace of it
  await page.waitForTimeout(1500);
  expect(asked).toEqual([]);
  await expect(page.locator("nav.pack-nav")).toHaveCount(0);

  await Promise.all([page.waitForEvent("load"), banner.getByRole("button").click()]);
  await expect(banner).toHaveCount(0);
  await expect.poll(() => asked.length, { timeout: 10_000 }).toBeGreaterThan(0);
});
