import AxeBuilder from "@axe-core/playwright";
import { expect, type Page, test } from "@playwright/test";
import { ASSISTANT, expectPersonalMenu, stubApi, themeCatalog } from "../../a11y/support";

// 027 — the universe themes on phones, tablets and desktops: each keeps every critical element of the
// header, never scrolls sideways, stays axe-clean, and uses the navigation principle it chose for the device.

const UNIVERSES: Array<[string, string]> = [
  ["wizard", "Grimoire"],
  ["galaxy", "Space Opera"],
  ["matrix", "Simulation"],
  ["desert", "Dune"],
  ["horror", "Horror"],
  ["halloween", "Halloween"],
  ["christmas", "Noël"],
  ["comic", "Comic"],
  ["manga", "Manga"],
  ["cartoon", "Cartoon"],
  ["cozy", "Cozy"],
  ["futuristic", "Neo Future"],
  ["minimal", "Minimal"],
  ["alien", "Xeno"],
  ["heroes", "Heroes"],
  ["neowave", "Neowave"],
  ["disco", "Disco"],
  ["cyberpunk", "Cyberpunk"],
];

async function signIn(page: Page) {
  await stubApi(page);
  await page.route("**/api/v1/ui/themes", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        themes: themeCatalog(["portalab-dark", "portalab-light", ...UNIVERSES.map(([key]) => key)]), // 028: the packs' interfaces, as the server serves them
        policy: {
          allowedThemes: ["portalab-dark", "portalab-light", ...UNIVERSES.map(([key]) => key)],
          defaultTheme: "portalab",
          textScaleMin: 0.85,
          textScaleMax: 2,
          forceReducedMotion: false,
        },
      }),
    }),
  );
  await page.goto("/");
  await page.getByLabel(/login/i).first().fill("alex");
  await page
    .getByLabel(/password/i)
    .first()
    .fill("correct horse battery");
  await page.keyboard.press("Enter");
  await expect(page.getByRole("banner")).toBeVisible();
}

for (const [key, name] of UNIVERSES) {
  test(`universe ${name} on phone, tablet and desktop`, async ({ page }) => {
    test.setTimeout(90_000);
    await page.setViewportSize({ width: 1440, height: 900 });
    await signIn(page);
    await page.goto("/settings/appearance");
    await page.getByRole("button", { name: new RegExp(`^${name}`) }).click();
    await expect.poll(() => page.evaluate(() => document.documentElement.dataset.theme)).toBe(key);
    for (const width of [390, 820, 1440]) {
      await page.setViewportSize({ width, height: 860 });
      await page.goto("/");
      await expectPersonalMenu(page);
      await expect(page.getByRole("button", { name: ASSISTANT })).toBeVisible();
      // its navigation on the page — or, for a menu in a panel or a sheet, the button opening it
      const opener = page.getByRole("button", { name: /^(Open navigation|Menu\b)/ });
      await expect(page.getByRole("navigation").or(opener).first()).toBeAttached();
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
      expect(overflow, `${name} at ${width}px`).toBeLessThanOrEqual(1);
      const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag22aa"]).analyze();
      expect(
        results.violations.map((v) => `${width}px ${v.id}: ${v.nodes[0]?.target}`),
        `${name} at ${width}px`,
      ).toEqual([]);
    }
  });
}
