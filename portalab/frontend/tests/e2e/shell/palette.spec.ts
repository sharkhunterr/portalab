import { expect, test } from "@playwright/test";
import { stubApi } from "../../a11y/support";

// 004 T027 — the palette opens from any page, lists only permitted commands, is keyboard-only, returns
// focus to where it was on close and announces results.

async function signIn(page: import("@playwright/test").Page) {
  await page.goto("/");
  await page.getByLabel(/login/i).first().fill("alex");
  await page
    .getByLabel(/password/i)
    .first()
    .fill("correct horse battery");
  await page.keyboard.press("Enter");
  await expect(page.getByRole("navigation", { name: "Main navigation" })).toBeVisible();
}

test("palette from any page, keyboard only", async ({ page }) => {
  await stubApi(page);
  await signIn(page);
  for (const path of ["/", "/services", "/account"]) {
    await page.goto(path);
    await expect(page.getByRole("navigation", { name: "Main navigation" })).toBeVisible();
    const trigger = page.getByRole("button", { name: /Search/ });
    await trigger.focus();
    await page.keyboard.press("Enter");
    const input = page.getByRole("combobox");
    await expect(input).toBeFocused();
    await expect(page.getByRole("option")).toHaveCount(4); // only what the server allowed
    await expect(page.getByTestId("announce-polite")).toContainText("4 results");
    await page.keyboard.press("Escape");
    await expect(trigger).toBeFocused(); // focus returns to the trigger
  }
  await page.keyboard.press("Control+k");
  await page.keyboard.type("serv");
  await page.keyboard.press("ArrowDown");
  await page.keyboard.press("ArrowUp");
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(/\/services$/);
});
