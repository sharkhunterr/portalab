import { type BrowserContext, expect, type Page, test } from "@playwright/test";
import { newDashboard, stubApi } from "../../a11y/support";

// 009 T017 / 027 FR-040 — keyboard-only add / move / resize / hide with explicit buttons (no drag-only
// path); moves and resizes go into the edit session and persist on Save, then show in a second browser
// context; edit controls are at least 24 px targets.

async function signIn(page: Page, dashboard: ReturnType<typeof newDashboard>) {
  await stubApi(page, { dashboard });
  await page.goto("/");
  await page.getByLabel(/login/i).first().fill("alex");
  await page
    .getByLabel(/password/i)
    .first()
    .fill("correct horse battery");
  await page.keyboard.press("Enter");
  await expect(page.getByRole("heading", { level: 1, name: /Alex/ })).toBeVisible(); // greeting (027)
}

const titles = async (page: Page) => page.locator(".dashboard-grid .widget-frame h3").allTextContents();

test("personalize with the keyboard, persisted across devices", async ({ page, browser }) => {
  const dashboard = newDashboard();
  await signIn(page, dashboard);
  expect(await titles(page)).toEqual(["Welcome", "Services status"]);

  await page.getByRole("button", { name: "Customize" }).focus();
  await page.keyboard.press("Enter");
  await page.getByRole("button", { name: "Add a widget" }).focus();
  await page.keyboard.press("Enter");
  const drawer = page.getByRole("dialog", { name: "Widget catalog" });
  await drawer.getByRole("button", { name: "Add Notes" }).focus();
  await page.keyboard.press("Enter");
  await expect(drawer.getByRole("button", { name: "Add Notes" })).toHaveText("Added");
  await page.keyboard.press("Escape");
  await expect.poll(() => titles(page)).toEqual(["Welcome", "Services status", "Notes"]);

  const notes = page.getByRole("toolbar", { name: "Notes" });
  await notes.getByRole("button", { name: "Move up" }).focus();
  await page.keyboard.press("Enter");
  await expect.poll(() => titles(page)).toEqual(["Welcome", "Notes", "Services status"]);
  const welcome = page.getByRole("toolbar", { name: "Welcome" });
  await welcome.getByRole("button", { name: "Wider" }).focus();
  await page.keyboard.press("Enter");
  await welcome.getByRole("button", { name: "Hide" }).focus();
  await page.keyboard.press("Enter");
  await expect.poll(() => titles(page)).toEqual(["Notes", "Services status"]);

  for (const button of await page.getByRole("toolbar", { name: "Notes" }).getByRole("button").all()) {
    const box = await button.boundingBox();
    expect(Math.min(box?.width ?? 0, box?.height ?? 0)).toBeGreaterThanOrEqual(24);
  }
  await page.getByRole("button", { name: "Save" }).focus();
  await page.keyboard.press("Enter");
  await expect(page.getByRole("button", { name: "Customize" })).toBeVisible();

  const other: BrowserContext = await browser.newContext();
  const second = await other.newPage();
  await signIn(second, dashboard);
  await expect.poll(() => titles(second)).toEqual(["Notes", "Services status"]);
  expect(dashboard.instances.find((i) => i.widget_key === "t.welcome")).toMatchObject({ status: "hidden" });
  const storedNotes = dashboard.instances.find((i) => i.widget_key === "t.notes");
  const services = dashboard.instances.find((i) => i.widget_key === "t.services");
  expect(Number(storedNotes?.y) <= Number(services?.y)).toBe(true); // Notes took Services' place
  await other.close();
});
