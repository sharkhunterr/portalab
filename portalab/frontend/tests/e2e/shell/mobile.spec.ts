import { expect, test } from "@playwright/test";
import { NAVIGATION, stubApi } from "../../a11y/support";

// 004 T031 — at 360 px the navigation is a drawer with the same destinations as desktop; search, assistant
// and palette remain reachable; targets ≥ 24 px; touch/keyboard parity.

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
  const menu = page.getByRole("button", { name: "Menu" });
  await expect(menu).toBeVisible();
  await expect(page.getByRole("button", { name: /Search/ })).toBeVisible();
  await expect(page.getByRole("button", { name: /Assistant/ })).toBeVisible();
  await menu.tap();
  const drawer = page.getByRole("dialog", { name: "Main navigation" });
  const expected = NAVIGATION.groups.flatMap((g) => g.entries).length;
  await expect(drawer.getByRole("link")).toHaveCount(expected);
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
