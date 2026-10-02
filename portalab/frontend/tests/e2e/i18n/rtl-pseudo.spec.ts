import { expect, type Page, test } from "@playwright/test";
import { stubApi } from "../../a11y/support";

// 026 T026 — pseudo-locales: ``en-XA`` (accented, ~30 % longer) must not truncate critical information or
// overflow the page; ``ar-XB`` (right-to-left) mirrors the layout. ``lang``/``dir`` are set on <html>.

async function signIn(page: Page, pseudo: string) {
  await stubApi(page);
  await page.goto(`/?pseudo=${pseudo}`);
  await page.getByLabel(/login/i).first().fill("alex");
  await page
    .getByLabel(/password/i)
    .first()
    .fill("correct horse battery");
  await page.keyboard.press("Enter");
}

test("en-XA: lengthened text stays visible and the page does not overflow", async ({ page }) => {
  await signIn(page, "en-XA");
  const nav = page.getByRole("navigation", { name: /Màîñ ñàvîgàtîöñ/ });
  await expect(nav).toBeVisible();
  await expect(page.locator("html")).toHaveAttribute("lang", "en-XA");
  await expect(page.locator("html")).toHaveAttribute("dir", "ltr");
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
  );
  expect(overflow).toBeLessThanOrEqual(0);
  const clipped = await nav
    .locator("a")
    .evaluateAll(
      (links) =>
        links.filter((a) => a.scrollWidth > a.clientWidth + 1 && getComputedStyle(a).overflow === "hidden")
          .length,
    );
  expect(clipped).toBe(0);
});

test("ar-XB: layout is mirrored", async ({ page }) => {
  await signIn(page, "ar-XB");
  const nav = page.getByRole("navigation").first();
  await expect(nav).toBeVisible();
  await expect(page.locator("html")).toHaveAttribute("dir", "rtl");
  await expect(page.locator("html")).toHaveAttribute("lang", "ar-XB");
  const main = page.locator("main").first();
  const navBox = await nav.boundingBox();
  const mainBox = await main.boundingBox();
  expect(navBox && mainBox && navBox.x > mainBox.x).toBe(true); // the sidebar sits on the right
});
