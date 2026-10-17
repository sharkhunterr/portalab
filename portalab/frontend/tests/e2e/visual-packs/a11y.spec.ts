import AxeBuilder from "@axe-core/playwright";
import { expect, type Page, test } from "@playwright/test";
import { fakeAdmin, fixture, goTo, signIn } from "./admin-fake";

// 028 (T098): an accessibility sweep (axe, WCAG 2.1 A and AA) of the visual packs' administration — the
// Extensions hub's lists, each of a version's six steps, the widgets — on a desktop's, a tablet's and a
// phone's width. (The packs' own navigations are swept by navigation.spec.ts.)

const PAGES = [
  ["the visual packs", "/admin/visuals"],
  ["Analysis", "/admin/visuals/nordlys/1.0.0?step=analysis"],
  ["Security", "/admin/visuals/nordlys/1.0.0?step=security"],
  ["Test", "/admin/visuals/nordlys/1.0.0?step=test"],
  ["Review", "/admin/visuals/nordlys/1.0.0?step=review"],
  ["Validation", "/admin/visuals/nordlys/1.0.0?step=validation"],
  ["the widgets", "/admin/widgets"],
] as const;

async function sweep(page: Page): Promise<string[]> {
  const results = await new AxeBuilder({ page })
    .include("#main-content")
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
    .analyze();
  return results.violations.map((v) => `${v.id} (${v.nodes.length}): ${v.nodes[0]?.target.join(" ")}`);
}

for (const width of [1280, 768, 390]) {
  test(`the visual packs' administration is accessible at ${width} px`, async ({ page }) => {
    test.setTimeout(120_000);
    await signIn(page, width);
    const admin = fakeAdmin(page, fixture("nordlys"));
    await admin.install();
    await goTo(page, "/admin/visuals");
    await page.getByRole("button", { name: "Read the inbox" }).click();
    const found: Record<string, string[]> = {};
    for (const [name, path] of PAGES) {
      await goTo(page, path);
      await expect(page.locator("#main-content h1, #main-content h2").first()).toBeVisible();
      await page.waitForTimeout(400); // the page settled (its queries answered)
      const violations = await sweep(page);
      if (violations.length) found[name] = violations;
    }
    expect(found).toEqual({});
  });
}
