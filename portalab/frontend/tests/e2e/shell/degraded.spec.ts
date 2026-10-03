import { expect, test } from "@playwright/test";
import { stubApi } from "../../a11y/support";

// 004 T021 — several failing services ⇒ one banner; navigation, search and palette keep working; a page
// whose data fails reports its own state with a retry while the shell stays usable.

test("degraded mode keeps the shell usable", async ({ page }) => {
  await stubApi(page, { failing: ["Media", "Books"] });
  await page.goto("/");
  await page.getByLabel(/login/i).first().fill("alex");
  await page
    .getByLabel(/password/i)
    .first()
    .fill("correct horse battery");
  await page.keyboard.press("Enter");
  await expect(page.getByText(/2 services are degraded or unavailable/)).toBeVisible();
  await page
    .getByRole("navigation", { name: "Main navigation" })
    .getByRole("link", { name: "Services" })
    .click();
  await expect(page).toHaveURL(/\/services$/);
  await page.keyboard.press("Control+k");
  await expect(page.getByRole("combobox")).toBeVisible();
  await page.keyboard.press("Escape");
  await page.route("**/api/v1/me/privacy", (route) =>
    route.fulfill({ status: 503, body: "{}", contentType: "application/json" }),
  );
  await page.goto("/privacy");
  await expect(page.getByRole("navigation", { name: "Main navigation" })).toBeVisible();
  await expect(page.getByRole("button", { name: /Search/ })).toBeEnabled();
});
