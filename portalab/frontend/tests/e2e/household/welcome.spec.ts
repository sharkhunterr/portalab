import { expect, type Page, test } from "@playwright/test";
import { becomeProfile, expectNoOverflow, signIn, stubPortal } from "../support/portal";

// Issues 443–450 — the welcome on a phone, every screen within its width: a master makes a household (its
// economy, a profile), a household profile chooses its own PIN and is never asked about e-mails.

test.use({ viewport: { width: 390, height: 820 }, hasTouch: true });

async function next(page: Page, where: string) {
  await expectNoOverflow(page, where);
  await page.getByRole("button", { name: "Next" }).click();
}

test("a master makes a household in the welcome", async ({ page }) => {
  test.setTimeout(60_000);
  const { state } = await stubPortal(page, { welcome: true, made: false });
  await signIn(page);
  const dialog = page.getByRole("dialog");
  await dialog.getByRole("button", { name: "Let's go" }).click();
  await expect(dialog.getByRole("heading", { name: "A face and a name" })).toBeVisible();
  await expect(dialog.getByRole("radio", { name: /Français/ })).toBeVisible(); // the languages by their flags
  await next(page, "a face and a name");
  await expect(dialog.getByRole("heading", { name: "Your media accounts" })).toBeVisible();
  await next(page, "the media accounts");
  await expect(dialog.getByRole("heading", { name: "A household?" })).toBeVisible();
  await expectNoOverflow(page, "a household?");
  await dialog.getByRole("button", { name: /Make my household/ }).click();
  await expect(dialog.getByRole("heading", { name: "How your household earns" })).toBeVisible();
  await dialog.getByRole("radio", { name: /Separate profiles/ }).check();
  await expect.poll(() => state.economy).toBe("dispatch");
  await next(page, "the household's economy");
  await expect(dialog.getByRole("heading", { name: "Your family" })).toBeVisible();
  await dialog.getByLabel("First name").fill("Léa");
  await dialog.getByRole("button", { name: "Add this profile" }).click();
  await expect.poll(() => state.profiles.map((p) => p.display_name)).toEqual(["Léa"]);
  await next(page, "the family");
  await expect(dialog.getByRole("heading", { name: "Each profile's rules" })).toBeVisible();
  await next(page, "each profile's rules");
  await expect(dialog.getByRole("heading", { name: "How far do you want to play?" })).toBeVisible();
  await expectNoOverflow(page, "how far to play");
});

test("a household profile chooses its PIN, and no e-mail", async ({ page }) => {
  test.setTimeout(60_000);
  const { state } = await stubPortal(page, { welcome: true, made: true });
  await signIn(page);
  await page.evaluate(() => window.localStorage.clear()); // its master's mirror on this browser is not its
  await becomeProfile(page);
  const dialog = page.getByRole("dialog");
  await dialog.getByRole("button", { name: "Let's go" }).click();
  await next(page, "a face and a name");
  await expect(dialog.getByRole("heading", { name: "Your PIN" })).toBeVisible();
  await dialog.getByLabel("New PIN").fill("1234");
  await dialog.getByLabel("The same PIN again").fill("1234");
  await dialog.getByRole("button", { name: "Save my PIN" }).click();
  await expect.poll(() => state.pins).toEqual([{ pin: "1234" }]);
  await next(page, "the PIN");
  await expect(dialog.getByRole("heading", { name: "How far do you want to play?" })).toBeVisible();
  await next(page, "how far to play");
  await expect(dialog.getByRole("heading", { name: "Your portal, to your taste" })).toBeVisible();
  await next(page, "the portal to taste");
  await expect(dialog.getByRole("heading", { name: "How should we tell you?" })).toBeVisible();
  await expect(dialog.getByText("By e-mail")).toHaveCount(0); // its master's account holds the e-mails
  await expectNoOverflow(page, "how to be told");
});
