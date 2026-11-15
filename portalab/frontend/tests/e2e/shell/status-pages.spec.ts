import { expect, test } from "@playwright/test";
import { expectNoOverflow, signIn, stubPortal } from "../support/portal";

// Issue 448 — the pages between pages look alike and never strand anyone: a page that is not there, an
// administration page for a member whose menu holds none.

test.use({ viewport: { width: 390, height: 800 }, hasTouch: true });

test("a page that is not there leads back home", async ({ page }) => {
  await stubPortal(page);
  await signIn(page);
  await page.goto("/nowhere-at-all");
  await expect(page.getByRole("heading", { name: "This page is not here" })).toBeVisible();
  await expect(page.getByRole("banner")).toBeVisible(); // within the portal: the header stays
  await expectNoOverflow(page, "the page not here");
  await page.getByRole("link", { name: "Back to the home page" }).click();
  await expect(page).toHaveURL(/\/$/);
});

test("the administration is not open to a member", async ({ page }) => {
  await stubPortal(page, { admin: false });
  await signIn(page);
  await page.goto("/admin/gamification");
  await expect(page.getByRole("heading", { name: "This page is not open to you" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Back to the home page" })).toHaveAttribute("href", "/");
  await expectNoOverflow(page, "the page not open");
});
