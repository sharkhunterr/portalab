import { type BrowserContext, expect, type Page, test } from "@playwright/test";
import { newDashboard, stubApi } from "../../a11y/support";

// 009 T017 / 027 FR-040 — keyboard-only add / move / resize / remove (no drag-only path: the grip takes
// Enter, then the arrow keys, Shift to resize); moves and resizes go into the edit session and persist on
// Save, then show in a second browser context; edit controls are at least 24 px targets.

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
  // 027: an added widget goes to « Already on your dashboard », marked « Added »
  const placed = drawer.getByRole("region", { name: "Already on your dashboard" });
  await expect(placed.getByRole("listitem").filter({ hasText: "Notes" })).toContainText("Added");
  await expect(drawer.getByRole("button", { name: "Add Notes" })).toHaveCount(0);
  await page.keyboard.press("Escape");
  await expect.poll(() => titles(page)).toEqual(["Welcome", "Services status", "Notes"]);

  // Notes (first free row) takes Services' place: grab, right to its column, up to the top row, drop
  const grip = page.getByRole("button", { name: "Move or resize Notes" });
  await grip.focus();
  await page.keyboard.press("Enter");
  await expect(grip).toHaveAttribute("aria-pressed", "true");
  for (let step = 0; step < 6; step++) await page.keyboard.press("ArrowRight");
  for (let step = 0; step < 2; step++) await page.keyboard.press("ArrowUp");
  await page.keyboard.press("Shift+ArrowRight"); // and one column wider
  await page.keyboard.press("Enter");
  await expect(grip).toHaveAttribute("aria-pressed", "false");
  await expect.poll(() => titles(page)).toEqual(["Welcome", "Notes", "Services status"]);

  await page.getByRole("toolbar", { name: "Welcome" }).getByRole("button", { name: "Remove" }).focus();
  await page.keyboard.press("Enter");
  await expect.poll(() => titles(page)).toEqual(["Notes", "Services status"]);

  const tools = page.getByRole("toolbar", { name: "Notes" }).getByRole("button");
  for (const button of [...(await tools.all()), grip]) {
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
  expect(dashboard.instances.find((i) => i.widget_key === "t.welcome")).toBeUndefined(); // removed
  const storedNotes = dashboard.instances.find((i) => i.widget_key === "t.notes");
  const services = dashboard.instances.find((i) => i.widget_key === "t.services");
  expect(storedNotes).toMatchObject({ x: 6, y: 0, w: 5 }); // Notes took Services' place, one column wider
  expect(Number(services?.y)).toBeGreaterThanOrEqual(2); // Services made room below
  await other.close();
});
