import { expect, type Page, test } from "@playwright/test";
import { newDashboard, stubApi } from "../../a11y/support";

// 027 T079 — desktop: Customize, drag a widget with the mouse, resize it by its corner, Save — the stored
// arrangement is what the preview showed; the keyboard path (Enter, arrows, Shift+arrows) does the same;
// Cancel restores; phones show the derived view (one or two columns, same reading order).

async function signIn(page: Page, width: number) {
  const dashboard = newDashboard();
  await page.setViewportSize({ width, height: 900 });
  await stubApi(page, { dashboard });
  await page.goto("/");
  await page.getByLabel(/login/i).first().fill("alex");
  await page
    .getByLabel(/password/i)
    .first()
    .fill("correct horse battery");
  await page.keyboard.press("Enter");
  await expect(page.getByRole("list", { name: "Dashboard" })).toBeVisible();
  return dashboard;
}

const cellOf = (page: Page, title: string) =>
  page
    .getByRole("list", { name: "Dashboard" })
    .locator("li", { has: page.getByRole("heading", { name: title }) });

test("drag and save with the mouse", async ({ page }) => {
  const dashboard = await signIn(page, 1440);
  await page.getByRole("button", { name: "Customize" }).click();
  const services = cellOf(page, "Services status");
  const welcome = cellOf(page, "Welcome");
  const target = await welcome.boundingBox();
  const grip = services.getByRole("button", { name: /Move or resize Services status/ });
  const from = await grip.boundingBox();
  if (!target || !from) throw new Error("no boxes");
  // drop the Services widget onto the Welcome widget's place: Welcome makes room below
  await page.mouse.move(from.x + from.width / 2, from.y + from.height / 2);
  await page.mouse.down();
  await page.mouse.move(from.x - (from.x - target.x) + 10, from.y + 5, { steps: 12 });
  await page.mouse.up();
  const box = (await services.boundingBox()) ?? { x: 0, y: 0 };
  expect(Math.abs(box.x - target.x)).toBeLessThan(20);
  expect((await welcome.boundingBox())?.y ?? 0).toBeGreaterThan(box.y + 20);
  await page.getByRole("button", { name: "Save" }).click();
  await expect(page.getByRole("button", { name: "Customize" })).toBeVisible();
  const saved = dashboard.arrangements?.at(-1) ?? [];
  const stored = saved.find((i) => i.id === dashboard.instances[1]?.id);
  expect(stored).toMatchObject({ x: 0, y: 0 });
  await page.reload();
  await expect(cellOf(page, "Services status")).toBeVisible();
  expect(Math.abs(((await cellOf(page, "Services status").boundingBox())?.x ?? 0) - target.x)).toBeLessThan(
    20,
  );
});

test("keyboard path, and Cancel restores", async ({ page }) => {
  const dashboard = await signIn(page, 1440);
  await page.getByRole("button", { name: "Customize" }).click();
  const grip = cellOf(page, "Welcome").getByRole("button", { name: /Move or resize Welcome/ });
  await grip.focus();
  await page.keyboard.press("Enter");
  await expect(grip).toHaveAttribute("aria-pressed", "true");
  await page.keyboard.press("Shift+ArrowLeft"); // narrower
  await page.keyboard.press("ArrowDown");
  await page.keyboard.press("Enter");
  await page.getByRole("button", { name: "Cancel" }).click();
  expect(dashboard.arrangements ?? []).toHaveLength(0); // nothing was sent
  await page.getByRole("button", { name: "Customize" }).click();
  const again = cellOf(page, "Welcome").getByRole("button", { name: /Move or resize Welcome/ });
  await again.focus();
  await page.keyboard.press("Enter");
  await page.keyboard.press("Shift+ArrowLeft");
  await page.keyboard.press("Enter");
  await page.getByRole("button", { name: "Save" }).click();
  const welcome = (dashboard.arrangements?.at(-1) ?? []).find((i) => i.id === dashboard.instances[0]?.id);
  expect(welcome?.w).toBe(5);
});

test("phones show the derived view in reading order", async ({ page }) => {
  await signIn(page, 390);
  const cells = page.getByRole("list", { name: "Dashboard" }).locator(":scope > li");
  await expect(cells).toHaveCount(2);
  const [first, second] = [await cells.nth(0).boundingBox(), await cells.nth(1).boundingBox()];
  expect((second?.y ?? 0) > (first?.y ?? 0)).toBe(true); // stacked, same order
  await page.getByRole("button", { name: "Customize" }).click();
  await expect(page.getByRole("button", { name: /Move or resize/ })).toHaveCount(0); // no drag on phones
  await expect(page.getByRole("button", { name: "Move down" }).first()).toBeVisible();
});
