import { expect, test } from "@playwright/test";
import { NAVIGATION, stubApi } from "../../a11y/support";

// Issue 452 — the site identity page (and its system language card) fits a phone's width: nothing wider
// than the screen, so the page never slides sideways.

test.use({ viewport: { width: 412, height: 900 }, hasTouch: true });

test("the site identity page fits a phone", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("console", (message) => {
    if (message.type() === "error") errors.push(message.text().slice(0, 300));
  });
  await stubApi(page);
  const json = (body: unknown) => ({
    status: 200,
    contentType: "application/json",
    body: JSON.stringify(body),
  });
  await page.route("**/api/v1/me/navigation", (route) =>
    route.fulfill(
      json({
        ...NAVIGATION,
        sections: [
          ...NAVIGATION.sections,
          {
            key: "admin",
            label_key: "nav.section.admin",
            audience: "administration",
            direct: false,
            topics: [],
            entries: [{ key: "shell.admin.site", label_key: "nav.admin.site", route: "/admin/site" }],
          },
        ],
      }),
    ),
  );
  await page.route("**/api/v1/i18n/languages", (route) =>
    route.fulfill(
      json({
        default: "en",
        items: [
          { code: "en", name_native: "English" },
          { code: "fr", name_native: "Français" },
        ],
      }),
    ),
  );
  await page.route("**/api/v1/admin/config", (route) =>
    route.fulfill(
      json({
        settings: [
          { key: "i18n.systemLanguage", value: "fr-FR", source: "global" },
          { key: "i18n.defaultLocale", value: "fr-FR", source: "global" },
          { key: "i18n.defaultLanguage", value: "fr", source: "global" },
        ],
      }),
    ),
  );
  await page.route("**/api/v1/admin/site", (route) =>
    route.fulfill(
      json({
        name: "Starport",
        default_name: "Portalab",
        tagline: {},
        currency: {},
        currency_short: "XC",
        currency_icon: "",
        logo: null,
        icon: null,
      }),
    ),
  );
  await page.goto("/");
  await page.getByLabel(/login/i).first().fill("alex");
  await page
    .getByLabel(/password/i)
    .first()
    .fill("correct horse battery");
  await page.keyboard.press("Enter");
  await page.goto("/admin/site");
  await page.waitForTimeout(1000);
  expect(errors.filter((e) => /TypeError|caught the following error/.test(e))).toEqual([]);
  await expect(page.getByRole("heading", { name: /System language and country/ })).toBeVisible();
  const wide = await page.evaluate(() =>
    [...document.querySelectorAll("body *")]
      .filter((el) => el.getBoundingClientRect().right > window.innerWidth + 1)
      .slice(0, 8)
      .map(
        (el) =>
          `${el.tagName.toLowerCase()}.${String(el.className).split(" ")[0]} ${Math.round(el.getBoundingClientRect().right)}`,
      ),
  );
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect({ overflow, wide }).toEqual({ overflow: 0, wide: [] });
});
