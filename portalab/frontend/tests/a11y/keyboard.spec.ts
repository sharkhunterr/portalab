import { expect, test } from "@playwright/test";
import { stubApi } from "./support";

// 022 T020 — keyboard-only journey sign-in → shell → appearance settings; visible focus; no focus trap;
// targets at least 24×24 CSS px; no drag-only interaction.

test("keyboard-only: sign in, reach and change appearance settings", async ({ page }) => {
  const { saved } = await stubApi(page);
  await page.goto("/");
  await page.keyboard.press("Tab");
  const login = page.getByLabel(/login/i).first();
  await login.focus();
  await page.keyboard.type("alex");
  await page.keyboard.press("Tab");
  await page.keyboard.type("correct horse battery");
  await page.keyboard.press("Enter");
  await expect(page.getByRole("navigation", { name: "Main navigation" })).toBeVisible();
  await page.keyboard.press("Control+k"); // command palette → appearance settings, keyboard only
  await page.keyboard.type("appear");
  await page.keyboard.press("Enter");
  const theme = page.getByLabel("Theme", { exact: true });
  await expect(theme).toBeVisible();
  for (let i = 0; i < 60 && !(await theme.evaluate((el) => el === document.activeElement)); i += 1) {
    await page.keyboard.press("Tab");
  }
  await expect(theme).toBeFocused();
  const outline = await theme.evaluate((el) => getComputedStyle(el).outlineStyle);
  expect(outline).not.toBe("none"); // visible focus
  await page.keyboard.press("ArrowDown"); // first option after "Portal default": Light
  await page.keyboard.press("ArrowDown");
  await expect.poll(() => page.evaluate(() => document.documentElement.dataset.theme)).toBe("dark");
  await expect.poll(() => saved["ui.theme"]).toBe("dark");
});

test("gallery: no focus trap, focus always visible, targets ≥ 24 px", async ({ page }) => {
  await page.goto("/dev/gallery");
  const seen = new Set<string>();
  for (let i = 0; i < 80; i += 1) {
    await page.keyboard.press("Tab");
    const info = await page.evaluate(() => {
      const el = document.activeElement as HTMLElement | null;
      if (!el || el === document.body) return null;
      const box = el.getBoundingClientRect();
      const style = getComputedStyle(el);
      return {
        key: `${el.tagName}:${el.textContent?.slice(0, 20)}:${el.getAttribute("aria-label") ?? el.id}`,
        visibleFocus: style.outlineStyle !== "none" || style.boxShadow !== "none",
        inline: el.tagName === "A" && style.display === "inline",
        width: box.width,
        height: box.height,
      };
    });
    if (!info) continue;
    seen.add(info.key);
    expect(info.visibleFocus, info.key).toBe(true);
    if (!info.inline) {
      expect(Math.min(info.width, info.height), info.key).toBeGreaterThanOrEqual(24);
    }
  }
  expect(seen.size).toBeGreaterThan(15); // focus kept moving: nothing trapped it
  await expect(page.locator('[draggable="true"]')).toHaveCount(0); // no drag-only interaction
});

test("dialog: Escape closes and focus returns to the trigger", async ({ page }) => {
  await page.goto("/dev/gallery");
  const trigger = page.getByRole("button", { name: "Open dialog" });
  await trigger.focus();
  await page.keyboard.press("Enter");
  await expect(page.getByRole("dialog", { name: "Confirm" })).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(trigger).toBeFocused();
});
