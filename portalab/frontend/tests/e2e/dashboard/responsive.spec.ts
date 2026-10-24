import { expect, type Page, test } from "@playwright/test";
import { newDashboard, stubApi } from "../../a11y/support";

// 009 T032 — large: widgets side by side; small: one column in the same order; reading order = DOM order =
// layout order; personalization reachable on mobile; no horizontal scroll at 320 px.

async function open(page: Page) {
  await stubApi(page, { dashboard: newDashboard() });
  await page.goto("/");
  await page.getByLabel(/login/i).first().fill("alex");
  await page
    .getByLabel(/password/i)
    .first()
    .fill("correct horse battery");
  await page.keyboard.press("Enter");
  await expect(page.locator(".dashboard-grid .widget-frame")).toHaveCount(2);
}

async function boxes(page: Page) {
  return Promise.all(
    (await page.locator(".dashboard-grid__cell").all()).map(async (cell) => cell.boundingBox()),
  );
}

test("large screens place widgets side by side", async ({ page }) => {
  await page.setViewportSize({ width: 1600, height: 900 });
  await open(page);
  const [first, second] = await boxes(page);
  expect(first && second && Math.abs(first.y - second.y) < 2 && second.x > first.x).toBe(true);
});

for (const width of [360, 320]) {
  test(`${width}px: one column, same order, no horizontal scroll`, async ({ page }) => {
    await page.setViewportSize({ width, height: 800 });
    await open(page);
    const [first, second] = await boxes(page);
    expect(first && second && second.y > first.y && Math.abs(first.x - second.x) < 2).toBe(true);
    expect(await page.locator(".dashboard-grid .widget-frame h3").allTextContents()).toEqual([
      "Welcome",
      "Services status",
    ]);
    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
    );
    expect(overflow).toBeLessThanOrEqual(0);
    await page.getByRole("button", { name: "Customize" }).click();
    // 027: on a phone too, a widget is moved by its grip (Enter, then the arrow keys) beside its tools
    await expect(page.getByRole("button", { name: "Move or resize Welcome" })).toBeVisible();
    await expect(page.getByRole("toolbar", { name: "Welcome" })).toBeVisible();
    const editing = await page.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
    );
    expect(editing).toBeLessThanOrEqual(0);
  });
}
