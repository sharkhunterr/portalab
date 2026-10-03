import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import { stubApi } from "../../a11y/support";

// 011 T024 — calendar month/week/list views, keyboard navigation, type legend with icon + text (never
// color alone), a banner for the one failing source, usable on a phone; no axe violations.

async function signIn(page: import("@playwright/test").Page) {
  await page.goto("/");
  await page.getByLabel(/login/i).first().fill("alex");
  await page
    .getByLabel(/password/i)
    .first()
    .fill("correct horse battery");
  await page.keyboard.press("Enter");
  await expect(page.getByRole("button", { name: /Search/ })).toBeVisible();
}

async function stubCalendar(page: import("@playwright/test").Page) {
  const now = new Date();
  const at = (days: number, hour: number) =>
    new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate() + days, hour)).toISOString();
  await page.route("**/api/v1/calendar?**", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        items: [
          {
            source_kind: "maintenance",
            source_id: "m1",
            type: "maintenance",
            title: "Database upgrade",
            starts_at: at(1, 9),
            ends_at: at(1, 10),
            date: null,
            all_day: false,
            reference_tz: null,
            status: "scheduled",
            url_ref: "/services",
          },
          {
            source_kind: "news",
            source_id: "n1",
            type: "publication",
            title: "Release notes",
            starts_at: at(2, 12),
            ends_at: null,
            date: null,
            all_day: false,
            reference_tz: null,
            status: "scheduled",
            url_ref: "/news/release-notes",
          },
        ],
        source_states: { maintenance: "ok", news: "ok", campaigns: "unavailable" },
        sources: {
          maintenance: "calendar:source.maintenance",
          news: "calendar:source.news",
          campaigns: "Campaigns",
        },
        lead_options: [15, 60],
        as_of: now.toISOString(),
      }),
    }),
  );
  await page.route("**/api/v1/me/calendar/reminders", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: "[]" }),
  );
}

test("calendar views, legend and source banner, keyboard only", async ({ page }) => {
  await stubApi(page);
  await stubCalendar(page);
  await signIn(page);
  await page.goto("/calendar");
  await expect(page.getByRole("heading", { name: "Calendar" })).toBeVisible();
  const legend = page.getByRole("list", { name: "Legend" });
  await expect(legend).toContainText("Maintenance");
  await expect(legend).toContainText("Publication");
  await expect(page.getByRole("status").filter({ hasText: "Campaigns" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Database upgrade" })).toBeVisible();
  const week = page.getByRole("button", { name: "Week" });
  await week.focus();
  await page.keyboard.press("Enter");
  await expect(week).toHaveAttribute("aria-pressed", "true");
  const list = page.getByRole("button", { name: "List" });
  await list.focus();
  await page.keyboard.press("Enter");
  await expect(page.getByRole("link", { name: "Release notes" })).toBeVisible();
  const results = await new AxeBuilder({ page }).include(".calendar-page").analyze();
  expect(results.violations).toEqual([]);
});

test("calendar on a phone", async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 800 });
  await stubApi(page);
  await stubCalendar(page);
  await signIn(page);
  await page.goto("/calendar");
  await expect(page.getByRole("link", { name: "Database upgrade" })).toBeVisible();
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1);
  expect(overflow).toBe(false);
});
