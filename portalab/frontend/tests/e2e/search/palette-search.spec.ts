import { expect, type Page, test } from "@playwright/test";
import { stubApi } from "../../a11y/support";

// 008 T028 — Mod+K on a service page shows its context actions; search results appear inside the palette;
// a destructive action asks for confirmation; the whole flow works with the keyboard and focus returns.

async function signIn(page: Page) {
  await stubApi(page);
  await page.goto("/");
  await page.getByLabel(/login/i).first().fill("alex");
  await page
    .getByLabel(/password/i)
    .first()
    .fill("correct horse battery");
  await page.keyboard.press("Enter");
  await expect(page.getByRole("navigation", { name: "Main navigation" })).toBeVisible();
}

test("palette: context actions, inline results, confirmation, keyboard only", async ({ page }) => {
  await signIn(page);
  await page.getByRole("link", { name: "Services" }).click();
  await page.goto("/services/s1");
  const trigger = page.getByRole("button", { name: /Search/ });
  await trigger.focus();
  await page.keyboard.press("Control+k");
  const input = page.getByRole("combobox");
  await expect(input).toBeFocused();
  await input.fill("restart");
  const list = page.getByRole("listbox");
  await expect(list.getByRole("option", { name: "Restart service" })).toBeVisible();
  await expect(list.getByRole("option", { name: "Search for “restart”" })).toBeVisible();
  const options = await list.getByRole("option").allTextContents();
  for (let i = 0; i < options.indexOf("Restart service"); i++) await page.keyboard.press("ArrowDown");
  await page.keyboard.press("Enter");
  const palette = page.getByRole("dialog");
  await expect(palette.getByRole("alert")).toContainText("needs confirmation");
  await expect(page).toHaveURL(/\/services\/s1$/); // nothing ran yet
  await page.keyboard.press("Escape"); // cancel the confirmation, palette stays
  await expect(palette.getByRole("alert")).toHaveCount(0);

  await input.fill("media");
  await expect(list.getByRole("option", { name: "Media server" })).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("combobox")).toHaveCount(0);
  await expect(trigger).toBeFocused(); // focus restored

  await page.keyboard.press("Control+k");
  await page.getByRole("combobox").fill("media");
  const full = page.getByRole("option", { name: "Search for “media”" });
  await expect(full).toBeVisible();
  await full.click();
  await expect(page).toHaveURL(/\/search\?q=media$/);
  await expect(page.getByRole("link", { name: "Media server (media)" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Assistant analysis" })).toBeVisible();
});
