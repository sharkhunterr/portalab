import { expect, type Page, test } from "@playwright/test";
import { headerSearch, stubApi } from "../../a11y/support";

// 023 T017 (frontend) — with no plugin, a plugin URL shows an explicit state instead of a broken slot and the
// shell keeps working; with a plugin enabled, its declarative page renders from design-system blocks.

async function signIn(page: Page) {
  await page.goto("/");
  await page.getByLabel(/login/i).first().fill("alex");
  await page
    .getByLabel(/password/i)
    .first()
    .fill("correct horse battery");
  await page.keyboard.press("Enter");
  await expect(headerSearch(page)).toBeVisible();
}

test("a disabled plugin leaves no broken slot", async ({ page }) => {
  await stubApi(page);
  await page.route("**/api/v1/plugins/**", (route) =>
    route.fulfill({
      status: 404,
      contentType: "application/json",
      body: JSON.stringify({ code: "plugin.not_available", title: "Not found", status: 404 }),
    }),
  );
  await signIn(page);
  await page.goto("/plugins/hello/main");
  await expect(page.getByText("This page is not available.")).toBeVisible();
  await expect(headerSearch(page)).toBeVisible();
});

test("an enabled plugin page renders its blocks", async ({ page }) => {
  await stubApi(page);
  await page.route("**/api/v1/plugins/hello/pages/main", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        plugin: "hello",
        key: "main",
        title_key: "Hello",
        blocks: [{ kind: "markdown", html: "<p>A <strong>declarative</strong> page</p>" }],
      }),
    }),
  );
  await signIn(page);
  await page.goto("/plugins/hello/main");
  await expect(page.getByRole("heading", { level: 1, name: "Hello" })).toBeVisible();
  await expect(page.getByText("declarative")).toBeVisible();
});
