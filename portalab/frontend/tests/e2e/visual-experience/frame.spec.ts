import AxeBuilder from "@axe-core/playwright";
import { expect, type Page, test } from "@playwright/test";
import { stubApi } from "../../a11y/support";

// 027 T029/T041/T047 — the personal header (avatar, level + XP, Coins, notifications, search, assistant,
// personal menu) at phone, tablet and desktop widths; sections in the navigation and personal pages in the
// avatar menu; no horizontal scroll from 320 px; axe clean on the frame.

async function signIn(page: Page) {
  await stubApi(page);
  await page.goto("/");
  await page.getByLabel(/login/i).first().fill("alex");
  await page
    .getByLabel(/password/i)
    .first()
    .fill("correct horse battery");
  await page.keyboard.press("Enter");
  await expect(page.getByRole("banner")).toBeVisible();
}

for (const [device, width, height] of [
  ["phone", 390, 844],
  ["tablet", 820, 1180],
  ["desktop", 1440, 900],
] as const) {
  test(`header and navigation on ${device}`, async ({ page }) => {
    await page.setViewportSize({ width, height });
    await signIn(page);
    const banner = page.getByRole("banner");
    await expect(banner.getByRole("img", { name: "Level 3" })).toBeVisible();
    await expect(banner.getByRole("img", { name: /Coins: 120/ })).toBeVisible();
    await expect(banner.getByRole("button", { name: /Assistant/ })).toBeVisible();
    await expect(banner.getByRole("button", { name: "Personal menu: Alex" })).toBeVisible();
    if (device === "phone") {
      const bar = page.getByRole("navigation", { name: "Sections" });
      await expect(bar.getByRole("button", { name: /Notifications/ })).toBeVisible();
      await expect(bar.getByRole("button", { name: /Search/ })).toBeVisible();
    } else {
      await expect(banner.getByRole("button", { name: /Notifications: 2 unread/ })).toBeVisible();
      await expect(banner.getByRole("button", { name: /Search/ })).toBeVisible();
      const nav = page.getByRole("navigation", { name: "Main navigation" });
      await expect(nav.getByRole("link", { name: "Services" })).toBeVisible();
    }
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    expect(overflow).toBeLessThanOrEqual(1);
    const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag22aa"]).analyze();
    expect(results.violations.map((v) => v.id)).toEqual([]);
  });
}

test("personal pages live in the avatar menu", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await signIn(page);
  await page.getByRole("button", { name: "Personal menu: Alex" }).click();
  const menu = page.getByRole("menu", { name: "Personal menu" });
  await expect(menu.getByRole("menuitem", { name: "Appearance" })).toBeVisible();
  await expect(menu.getByRole("menuitem", { name: "Sign out" })).toBeVisible();
  await menu.getByRole("menuitem", { name: "Appearance" }).click();
  await expect(page).toHaveURL(/\/settings\/appearance$/);
  const nav = page.getByRole("navigation", { name: "Main navigation" });
  await expect(nav.getByRole("link", { name: "Appearance" })).toHaveCount(0);
});

test("no horizontal scroll from 320 px, and the page survives a class change", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await signIn(page);
  for (const width of [320, 390, 820, 1440]) {
    await page.setViewportSize({ width, height: 800 });
    for (const path of ["/", "/services", "/account"]) {
      await page.goto(path);
      await page.waitForLoadState("networkidle");
      await expect(page.getByRole("main")).toBeVisible();
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
      expect(overflow, `${path} at ${width}px`).toBeLessThanOrEqual(1);
    }
  }
});
