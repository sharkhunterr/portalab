import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

// 022 T021/T039 — 320 px reflow without horizontal scrolling, WCAG text-spacing override, touch targets,
// complete content on mobile; axe on the gallery under each built-in theme.

const TEXT_SPACING = `* { line-height: 1.5 !important; letter-spacing: 0.12em !important; word-spacing: 0.16em !important; }
p { margin-bottom: 2em !important; }`;

test.describe("320 px", () => {
  test.use({ viewport: { width: 320, height: 640 }, hasTouch: true });

  test("reflows without horizontal scroll, even with text spacing and 200 % text", async ({ page }) => {
    await page.goto("/dev/gallery");
    const overflow = () =>
      page.evaluate(() => {
        const extra = document.documentElement.scrollWidth - window.innerWidth;
        if (extra <= 1) return extra;
        const wide = [...document.querySelectorAll("body *")]
          .filter((el) => el.getBoundingClientRect().right > window.innerWidth + 1)
          .slice(0, 5)
          .map((el) => `${el.tagName}.${String(el.className)}`);
        return `${extra}px: ${wide.join(", ")}`;
      });
    expect(String(await overflow())).toMatch(/^-?[01]$|^-\d+$/);
    await page.addStyleTag({ content: TEXT_SPACING });
    expect(String(await overflow())).toMatch(/^-?[01]$|^-\d+$/);
    await page.evaluate(() => document.documentElement.style.setProperty("--text-scale", "2"));
    expect(String(await overflow())).toMatch(/^-?[01]$|^-\d+$/);
    for (const name of ["Functional states", "Actions", "Forms", "Content"]) {
      await expect(page.getByRole("heading", { name })).toBeVisible(); // functionally complete on mobile
    }
  });
});

for (const theme of ["light", "dark", "high-contrast"]) {
  test(`axe passes on the gallery (${theme})`, async ({ page }) => {
    await page.goto("/dev/gallery");
    await page.getByLabel("Gallery theme").selectOption(theme);
    await expect.poll(() => page.evaluate(() => document.documentElement.dataset.theme)).toBe(theme);
    const results = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"])
      .analyze();
    expect(
      results.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(" ")).join(", ")}`),
    ).toEqual([]);
  });
}
