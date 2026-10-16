import { expect, type Page, test } from "@playwright/test";
import { newDashboard, stubApi } from "../../a11y/support";
import { element, sandboxTexts, servePack } from "./support";

// 028 T084 (US6, SC-009) — a pack's widget, self-contained: it is handed only the contracts it declared and
// the member may read (a forbidden one is never read), its own settings and its form (a line, a block); an
// option a member put on a Portalab widget shows it otherwise from that widget's own data; a frame's look
// dresses the widget. The real Vigie example and the real sandbox bootstrap, the API stubbed.

const META = (title: string, extra: Record<string, unknown> = {}) => ({
  title_key: title,
  description_key: null,
  icon: null,
  component_id: null,
  template: null,
  refresh_mode: "on_view",
  refresh_interval_s: null,
  min_w: 2,
  min_h: 1,
  max_w: 12,
  max_h: 4,
  multiple: false,
  config_schema: { type: "object", properties: {} },
  ...extra,
});

async function open(page: Page) {
  const dashboard = newDashboard();
  const base = dashboard.instances[0] as Record<string, unknown>;
  dashboard.instances = [
    {
      ...base,
      id: "00000000-0000-7000-8000-0000000000a1",
      widget_key: "pack.vigie-cap",
      x: 0,
      y: 0,
      w: 6,
      h: 2,
      config: { dial: "silver", _skin: "vigie" },
      widget: META("Heading", { component_id: "visuals.pack" }),
    },
    {
      ...base,
      id: "00000000-0000-7000-8000-0000000000a2",
      widget_key: "pack.vigie-cap",
      x: 6,
      y: 0,
      w: 6,
      h: 1,
      config: { dial: "night" },
      widget: META("Heading", { component_id: "visuals.pack" }),
    },
    {
      ...base,
      id: "00000000-0000-7000-8000-0000000000a3",
      widget_key: "media.recently_added",
      x: 0,
      y: 2,
      w: 12,
      h: 2,
      config: { _options: ["journal"] },
      widget: META("Recently added", { template: "list" }),
    },
  ];
  const read: string[] = [];
  await page.setViewportSize({ width: 1440, height: 1000 });
  await stubApi(page, { dashboard });
  await servePack(page, "widgets");
  await page.route("**/api/v1/visuals/active", (route) =>
    route.fulfill({
      json: {
        epoch: 1,
        withheld: {},
        elements: [
          element("vigie", "widget-cap", {
            product: "widget_vigie_cap",
            type: "widget",
            look: "vigie-cap",
            kind: "js",
            file: "cap.js",
            names: { en: "Heading" },
            contracts: ["me.progression", "me.statistics", "widget:media.recently_added"],
            widget: {
              sizes: [
                { w: 4, h: 2 },
                { w: 4, h: 1 },
              ],
              empty: { en: "Your heading shows soon." },
            },
          }),
          element("vigie", "style-vigie", {
            product: "widget_style_vigie",
            type: "widget_style",
            look: "vigie",
            kind: "css",
            css: ["frame.css"],
            names: { en: "Lacquer and brass" },
          }),
          element("vigie", "option-journal", {
            product: "widget_option_journal",
            type: "widget_option",
            look: "journal",
            kind: "js",
            file: "journal.js",
            names: { en: "The logbook" },
            contracts: ["me.watching"],
            widget: { for: "media.recently_added", place: "replace" },
          }),
        ],
      },
    }),
  );
  await page.route("**/api/v1/widgets/pack.vigie-cap/data**", (route) =>
    route.fulfill({
      json: {
        state: "available",
        as_of: null,
        stale_after_s: null,
        partial_reasons: [],
        config_invalid: false,
        data: {
          pack: "vigie",
          sha: "0123456789abcdef",
          look: "vigie-cap",
          contracts: ["me.progression", "me.statistics", "widget:media.recently_added", "me.secrets"],
          forbidden: ["widget:media.recently_added"],
        },
      },
    }),
  );
  await page.route("**/api/v1/me/streak", (route) =>
    route.fulfill({ json: { enabled: true, days: 4, multiplier: 1.5, freezes: 0, last_frozen: null } }),
  );
  await page.route("**/api/v1/me/media/continue", (route) =>
    route.fulfill({
      json: [
        {
          object_id: "o1",
          kind: "movie",
          title: "Dune",
          percent: 40,
          resume_position_s: 1,
          last_occurred_at: "2026-10-15T00:00:00Z",
        },
      ],
    }),
  );
  page.on("request", (request) => {
    const url = new URL(request.url());
    read.push(url.pathname + url.search);
  });
  await page.goto("/");
  await page.getByLabel(/login/i).first().fill("alex");
  await page
    .getByLabel(/password/i)
    .first()
    .fill("correct horse battery");
  await page.keyboard.press("Enter");
  await expect(page.getByRole("list", { name: "Dashboard" })).toBeVisible();
  return read;
}

test("a pack's widget gets only its readable contracts, its settings and its form", async ({ page }) => {
  const read = await open(page);
  await expect(page.locator('[data-widget="pack.vigie-cap"] iframe.pack-widget')).toHaveCount(2);
  await expect
    .poll(async () => (await sandboxTexts(page)).join("|"), { timeout: 15_000 })
    .toContain("Level 3");
  const texts = await sandboxTexts(page);
  // the block: its level, what remains, its coins; the line: the essentials on one line
  expect(texts.some((t) => t.includes("To level 4") && t.includes("120"))).toBe(true);
  expect(texts.some((t) => /Level 3\s*160 XP → 4\s*120 coins/.test(t))).toBe(true);
  // the contract the member may not read is never read; one the portal does not offer neither
  expect(read).toContain("/api/v1/me/progression");
  // (« Recently added » placed on the dashboard reads its own data, for its instance: not the contract)
  expect(read.filter((p) => p === "/api/v1/widgets/media.recently_added/data")).toHaveLength(0);
  expect(read.some((p) => p.startsWith("/api/v1/widgets/media.recently_added/data?instance="))).toBe(true);
  expect(read.filter((p) => p.startsWith("/api/v1/me/secrets"))).toHaveLength(0);
  // its frame wears the pack's look
  await expect(page.locator('[data-widget="pack.vigie-cap"][data-widget-style="vigie"]')).toHaveCount(1);
});

test("an option shows a Portalab widget otherwise, from its own data", async ({ page }) => {
  await open(page);
  const recent = page.locator('[data-widget="media.recently_added"]');
  await expect(recent).toHaveAttribute("data-widget-option", "journal");
  await expect(recent.locator("iframe.pack-widget")).toHaveCount(1);
  await expect
    .poll(async () => (await sandboxTexts(page)).join("|"), { timeout: 15_000 })
    .toContain("Logbook");
  expect((await sandboxTexts(page)).some((t) => t.includes("1 title in progress"))).toBe(true);
});
