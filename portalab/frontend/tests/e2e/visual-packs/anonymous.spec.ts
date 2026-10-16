import { expect, test } from "@playwright/test";

// 028 T051 (issue 135, SC-005) — the sign-in page is styled and usable while the portal answers a visitor only
// on its allow-list: every other address gets the very same 401, as the server does. Whatever the page asks
// for besides is refused and changes nothing; it asks for nothing of the members' pages. (That a guessed lazy
// chunk or its source map answers 401 without a session is the server's: tests/integration/
// test_anonymous_surface.py, and frontend/tests/unit/visuals/public-assets.test.ts for the build.)

const ALLOWED = new Set([
  "/api/v1/auth/login",
  "/api/v1/auth/logout",
  "/api/v1/auth/oidc",
  "/api/v1/auth/oidc/start",
  "/api/v1/auth/oidc/callback",
  "/api/v1/auth/register",
  "/api/v1/auth/verify",
  "/api/v1/auth/deletion/cancel",
  "/api/v1/admin/first-run",
]);
const CATALOGS = new Set(["auth", "common", "errors"]);
const GENERIC = { status: 401, title: "Unauthorized", code: "auth.required" };

test("the sign-in page works on the allow-list alone", async ({ page }) => {
  const asked: string[] = [];
  const refused: string[] = [];
  await page.route("**/api/v1/**", (route) => {
    const path = new URL(route.request().url()).pathname;
    asked.push(path);
    const catalog = /^\/api\/v1\/i18n\/catalogs\/([^/]+)$/.exec(path)?.[1];
    if (catalog && CATALOGS.has(catalog))
      return route.fulfill({ json: { namespace: catalog, messages: {} } });
    if (path === "/api/v1/auth/oidc") return route.fulfill({ json: { enabled: false, providers: [] } });
    if (ALLOWED.has(path))
      return route.fulfill({ status: 401, json: { code: "auth.invalid_credentials", title: "No" } });
    refused.push(path);
    return route.fulfill({
      status: 401,
      contentType: "application/problem+json",
      body: JSON.stringify(GENERIC),
    });
  });
  await page.setViewportSize({ width: 390, height: 800 });
  await page.goto("/");
  const login = page.getByLabel(/login/i).first();
  await expect(login).toBeVisible();
  // styled: the design system's stylesheet applied (not the browser's defaults)
  const font = await page.evaluate(() => getComputedStyle(document.body).fontFamily);
  expect(font).not.toMatch(/^"?Times/);
  // usable: a refused sign-in says so, the page stays
  await login.fill("alex");
  await page
    .getByLabel(/password/i)
    .first()
    .fill("wrong");
  await page.keyboard.press("Enter");
  await expect(page.getByRole("alert").first()).toBeVisible();
  await expect(login).toBeVisible();
  // what it asked besides the allow-list: only whether a session exists (the generic 401 says no)
  expect([...new Set(refused)]).toEqual(["/api/v1/me"]);
  expect(asked).toContain("/api/v1/auth/login");
});
