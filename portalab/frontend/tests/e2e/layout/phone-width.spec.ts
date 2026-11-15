import { test } from "@playwright/test";
import { expectNoOverflow, signIn, stubPortal } from "../support/portal";

// Issues 447–453 — at a phone's width, no page slides sideways: the home, My household, the notification
// settings, the account, a page that is not there, and the administration's site identity, gamification and
// setup assistant.

const PAGES = [
  "/",
  "/household",
  "/household/profiles",
  "/household/schedule",
  "/settings/notifications",
  "/account",
  "/nowhere-at-all",
  "/admin/site",
  "/admin/gamification",
  "/admin/setup",
];

for (const width of [360, 412]) {
  test.describe(`${width} px`, () => {
    test.use({ viewport: { width, height: 780 }, hasTouch: true });

    test("every page fits the screen", async ({ page }) => {
      test.setTimeout(90_000);
      await stubPortal(page, { admin: true });
      await signIn(page);
      for (const path of PAGES) {
        await page.goto(path);
        await page.waitForTimeout(900); // the page's data, and the status cards that come after a moment
        await expectNoOverflow(page, path);
      }
    });
  });
}
