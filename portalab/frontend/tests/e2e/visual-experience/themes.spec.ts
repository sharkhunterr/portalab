import AxeBuilder from "@axe-core/playwright";
import { expect, type Page, test } from "@playwright/test";
import { stubApi } from "../../a11y/support";

// 027 T062/T064 — themes change the arrangement principle, not only colors: Orbit puts the header at the
// bottom and the navigation in an orbit bubble, Studio uses a top bar; switching keeps the page and typed
// text, applies without reload, keeps every critical element, and stays axe-clean on phone and desktop.

const ALL = ["portalab-dark", "portalab-light", "orbit", "studio", "light", "dark", "high-contrast"];

async function signIn(page: Page) {
  await stubApi(page);
  await page.route("**/api/v1/ui/themes", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        themes: [],
        policy: {
          allowedThemes: ALL,
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

const nav = (page: Page) => page.evaluate(() => document.documentElement.dataset.navDesktop);

test("switching themes changes the layout principle without reload", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await signIn(page);
  await page.goto("/settings/appearance");
  const marker = await page.evaluate(() => {
    (window as unknown as { __stay: number }).__stay = 42;
    return true;
  });
  expect(marker).toBe(true);
  await page.getByRole("button", { name: /^Orbit/ }).click();
  await expect.poll(() => nav(page)).toBe("orbit");
  await expect(page.getByRole("button", { name: "Open navigation" })).toBeVisible();
  const header = await page.getByRole("banner").boundingBox();
  expect(header?.y ?? 0).toBeGreaterThan(700); // the header became a footer bar
  await page.getByRole("button", { name: "Open navigation" }).click();
  await expect(page.getByRole("dialog", { name: "Main navigation" })).toBeVisible();
  await page.keyboard.press("Escape");

  await page.getByRole("button", { name: /^Studio/ }).click();
  await expect.poll(() => nav(page)).toBe("topbar");
  expect((await page.getByRole("banner").boundingBox())?.y ?? 99).toBeLessThan(5);
  await expect(page.getByRole("navigation", { name: "Main navigation" })).toBeVisible();

  await page.getByRole("button", { name: /^Portalab/ }).click();
  await expect.poll(() => nav(page)).toBe("sidebar");
  // same document all along: no reload happened
  expect(await page.evaluate(() => (window as unknown as { __stay?: number }).__stay)).toBe(42);
  for (const critical of [/Search/, /Notifications/, /Assistant/, /Personal menu/]) {
    await expect(page.getByRole("banner").getByRole("button", { name: critical })).toBeVisible();
  }
});

for (const theme of ["Orbit", "Studio", "Portalab"]) {
  for (const [device, width] of [
    ["phone", 390],
    ["desktop", 1440],
  ] as const) {
    test(`axe and critical elements: ${theme} on ${device}`, async ({ page }) => {
      await page.setViewportSize({ width: 1440, height: 900 });
      await signIn(page);
      await page.goto("/settings/appearance");
      await page.getByRole("button", { name: new RegExp(`^${theme}`) }).click();
      await page.setViewportSize({ width, height: 860 });
      await page.goto("/");
      await expect(page.getByRole("banner").getByRole("button", { name: /Personal menu/ })).toBeVisible();
      await expect(page.getByRole("button", { name: /Assistant/ })).toBeVisible();
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
      expect(overflow).toBeLessThanOrEqual(1);
      const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag22aa"]).analyze();
      expect(results.violations.map((v) => `${v.id}: ${v.nodes[0]?.target}`)).toEqual([]);
    });
  }
}
