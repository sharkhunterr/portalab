import { expect, test } from "@playwright/test";
import { fakeAdmin, fixture, goTo, signIn } from "./admin-fake";

// 028 T020 (US1) — a pack from the inbox through the six steps, on a desktop's and a phone's width: Import,
// Analysis, Security, Test (measured in this browser), Review (the economy changed, the confirmations given),
// Validation (published). A pack the analysis blocks stops there: no way to publish it. The reports are the
// real analysis's (fixtures/ written by backend/scripts/e2e_visual_fixtures.py), the Admin API a fake.

for (const width of [1280, 390]) {
  test(`Nordlys from the inbox through the six steps at ${width} px`, async ({ page }) => {
    test.setTimeout(90_000);
    await signIn(page, width);
    const admin = fakeAdmin(page, fixture("nordlys"));
    await admin.install();
    await goTo(page, "/admin/visuals");
    await page.getByRole("button", { name: "Read the inbox" }).click();
    await page
      .getByRole("link", { name: /1\.0\.0/ })
      .first()
      .click();
    // the version opens at its next step: Analysis and Security done, Test waiting
    const stepper = page.getByRole("navigation", { name: /steps/i });
    await expect(stepper).toBeVisible();
    await expect(page.getByRole("button", { name: "Measure" })).toBeVisible();
    await page.getByRole("button", { name: "Measure" }).click();
    await expect.poll(() => admin.state.step, { timeout: 30_000 }).toBe("tested");
    // Review: a price changed, the script accepted
    await goTo(page, `/admin/visuals/nordlys/1.0.0?step=review`);
    const price = page.getByRole("spinbutton", { name: /^Price.* — / }).first();
    await price.fill("1234");
    const script = page.getByRole("checkbox", { name: /script/i });
    await script.check();
    await page.getByRole("button", { name: "Save the review" }).click();
    await expect.poll(() => admin.state.step).toBe("reviewed");
    // Validation: published, with the economy decided
    await page.getByRole("button", { name: "Validate and publish" }).click();
    await page.getByRole("dialog").getByRole("button", { name: "Validate and publish" }).click();
    await expect.poll(() => admin.state.step).toBe("published");
    expect(JSON.stringify(admin.state.published)).toContain("1234");
  });
}

test("a pack the analysis blocks stops at Analysis", async ({ page }) => {
  await signIn(page, 1280);
  const admin = fakeAdmin(page, fixture("blocked"));
  await admin.install();
  await goTo(page, "/admin/visuals");
  await page.getByRole("button", { name: "Read the inbox" }).click();
  await page
    .getByRole("link", { name: /1\.0\.0/ })
    .first()
    .click();
  // it opens on Analysis, the blocking finding said, and nothing lets it be published
  await expect(page.getByRole("link", { name: /Analysis/ })).toHaveAttribute("aria-current", "step");
  await expect(page.getByText(/missing\.css/).first()).toBeVisible();
  await goTo(page, "/admin/visuals/brouillon/1.0.0?step=validation");
  await expect(page.getByRole("button", { name: "Validate and publish" })).toBeDisabled();
  expect(admin.state.published).toBeNull();
});
