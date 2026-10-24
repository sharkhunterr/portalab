import { expect, test } from "@playwright/test";
import { ASSISTANT, NAVIGATION, stubApi } from "../../a11y/support";

// 004 T031 / 027 T047 — at 360 px the compact header gives Home, Search, Notifications and the Menu, whose
// drawer holds every section (and the profile); search, assistant and palette remain reachable; targets
// ≥ 24 px.

test.use({ viewport: { width: 360, height: 740 }, hasTouch: true });

test("mobile drawer has the full destination set", async ({ page }) => {
  await stubApi(page);
  await page.goto("/");
  await page.getByLabel(/login/i).first().fill("alex");
  await page
    .getByLabel(/password/i)
    .first()
    .fill("correct horse battery");
  await page.keyboard.press("Enter");
  // 027: the phone's default frame is the compact header with the menu in a panel (no bottom bar)
  const bar = page.getByRole("banner");
  const menu = bar.getByRole("button", { name: "Open navigation" });
  await expect(menu).toBeVisible();
  await expect(bar.getByRole("link", { name: "Home" })).toBeVisible();
  await expect(bar.getByRole("button", { name: "Search" })).toBeVisible();
  await expect(bar.getByRole("button", { name: /Notifications/ })).toBeVisible();
  await expect(page.getByRole("button", { name: ASSISTANT })).toBeVisible();
  await menu.tap();
  const drawer = page.getByRole("dialog", { name: "Main navigation" });
  const sections = drawer.getByRole("navigation", { name: "Main navigation" });
  const expected = NAVIGATION.sections.flatMap((s) => s.entries).length;
  await expect(sections.getByRole("link")).toHaveCount(expected);
  for (const link of await drawer.getByRole("link").all()) {
    const box = await link.boundingBox();
    expect(Math.min(box?.width ?? 0, box?.height ?? 0)).toBeGreaterThanOrEqual(24);
  }
  await drawer.getByRole("link", { name: "Services" }).tap();
  await expect(page).toHaveURL(/\/services$/);
  await expect(drawer).toHaveCount(0); // the drawer closes after navigating
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(overflow).toBeLessThanOrEqual(1);
});
