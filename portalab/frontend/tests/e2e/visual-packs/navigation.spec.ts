import { expect, type Page, test } from "@playwright/test";
import { stubApi } from "../../a11y/support";
import { element, packFile, servePack } from "./support";

// 028 T063 (US4) — an interface's navigation of its own (the real Abysses sonar, in the real sandbox): at a
// phone's, a tablet's and a desktop's width every section opens a page, with the mouse and with the keyboard;
// a navigation that fails gives way to a built-in one within 5 s; the administration keeps its own.

const INTERFACE = element("abysses", "interface-abysses", {
  product: "theme_abysses",
  type: "theme",
  look: "abysses",
  kind: "theme",
  file: "interface.json",
  css: ["interface.css"],
  names: { en: "Abysses interface" },
});
const SONAR = element("abysses", "nav-sonar", {
  product: "nav_sonar",
  type: "navigation",
  look: "sonar",
  kind: "js",
  file: "sonar.js",
  nav: { position: "bottom", size: 76, expands: true },
  names: { en: "Sonar" },
});

async function signIn(page: Page, width: number, navigation: Record<string, unknown> = SONAR) {
  await page.setViewportSize({ width, height: 900 });
  await stubApi(page);
  await servePack(page, "abysses");
  await page.route("**/api/v1/visuals/files/abysses/0123456789abcdef/broken/**", (route) =>
    route.fulfill({
      contentType: "text/javascript",
      body: "export default () => { throw new Error('broken'); };",
    }),
  );
  await page.route("**/api/v1/me/preferences", (route) =>
    route.fulfill({ json: { preferences: [{ key: "ui.theme", value: "abysses" }] } }),
  );
  await page.route("**/api/v1/ui/themes", (route) =>
    route.fulfill({
      json: {
        // the server lists the registered interfaces, a pack's among them
        themes: [
          { key: "abysses", definition: JSON.parse(packFile("abysses", "interface-abysses/interface.json")) },
        ],
        policy: {
          allowedThemes: ["light", "dark", "high-contrast", "abysses"],
          defaultTheme: "light",
          textScaleMin: 0.85,
          textScaleMax: 2,
          forceReducedMotion: false,
        },
      },
    }),
  );
  await page.route("**/api/v1/visuals/active", (route) =>
    route.fulfill({ json: { epoch: 1, withheld: {}, elements: [INTERFACE, navigation] } }),
  );
  await page.goto("/");
  await page.getByLabel(/login/i).first().fill("alex");
  await page
    .getByLabel(/password/i)
    .first()
    .fill("correct horse battery");
  await page.keyboard.press("Enter");
  // (its vocabulary renames the pages: the main content says it is there)
  await expect(page.locator("#main-content")).toBeVisible();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "abysses");
}

for (const width of [390, 820, 1280]) {
  test(`every section opens a page at ${width} px, by mouse and by keyboard`, async ({ page }) => {
    await signIn(page, width);
    const nav = page.locator("nav.pack-nav");
    await expect(nav).toBeVisible({ timeout: 10_000 });
    await expect(nav).toHaveAttribute("aria-label", /.+/); // the landmark stays Portalab's
    const sonar = page.frameLocator("iframe.pack-nav__frame");
    const echoes = sonar.locator("button.echo");
    await expect(echoes).toHaveCount(2);
    await echoes.nth(1).click(); // « Services »: one page, opened at once
    await expect(page).toHaveURL(/\/services$/);
    await page.waitForTimeout(450); // a navigation asks a few times a second at most
    await echoes.nth(0).focus(); // « Home », with the keyboard
    await page.keyboard.press("Enter");
    await expect(page).toHaveURL(/\/$/);
  });
}

test("a navigation that fails gives way to a built-in one within 5 s", async ({ page }) => {
  const loaded = page.waitForRequest((request) => request.url().includes("/broken/nav.js"));
  await signIn(page, 1280, { ...SONAR, file: SONAR.file?.replace("nav-sonar/sonar.js", "broken/nav.js") });
  await loaded; // the pack's navigation was tried…
  await expect(page.locator("nav.pack-nav")).toHaveCount(0, { timeout: 5_000 }); // …and gave way
  await expect(page.getByRole("navigation").first()).toBeVisible();
});

test("the administration keeps its own navigation", async ({ page }) => {
  await signIn(page, 1280);
  await expect(page.locator("nav.pack-nav")).toBeVisible({ timeout: 10_000 });
  await page.evaluate(() => window.history.pushState({}, "", "/admin/system"));
  await page.evaluate(() => window.dispatchEvent(new PopStateEvent("popstate")));
  await expect(page.locator("nav.pack-nav")).toHaveCount(0);
});
