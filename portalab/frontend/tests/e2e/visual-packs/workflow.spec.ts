import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { expect, type Page, type Route, test } from "@playwright/test";
import { stubApi } from "../../a11y/support";
import { serveCatalogs } from "./support";

// 028 T020 (US1) — a pack from the inbox through the six steps, on a desktop's and a phone's width: Import,
// Analysis, Security, Test (measured in this browser), Review (the economy changed, the confirmations given),
// Validation (published). A pack the analysis blocks stops there: no way to publish it. The reports are the
// real analysis's (fixtures/ written by backend/scripts/e2e_visual_fixtures.py), the Admin API a fake.

const HERE = dirname(fileURLToPath(import.meta.url));
const ROOT = resolve(HERE, "../../../..");
const fixture = (name: string) => JSON.parse(readFileSync(resolve(HERE, "fixtures", `${name}.json`), "utf8"));

type Step = "analysed" | "tested" | "reviewed" | "published";

function fakeAdmin(page: Page, fx: { report: Record<string, any>; elements: unknown[] }) {
  const pack = fx.report.pack.id as string;
  const version = fx.report.pack.version as string;
  const outcome = (category: string) => {
    const levels = new Set(
      (fx.report.items as Array<{ level: string; category: string }>)
        .filter((i) => i.category === category)
        .map((i) => i.level),
    );
    return levels.has("blocking") ? "blocking" : levels.has("warning") ? "warning" : "done";
  };
  const state = {
    scanned: false,
    step: "analysed" as Step,
    measures: null as unknown,
    draft: null as Record<string, unknown> | null,
    published: null as Record<string, unknown> | null,
  };
  const row = () => ({
    version,
    sha: "0123456789abcdef".repeat(4),
    step: state.step,
    outcomes: {
      import: "done",
      analysis: outcome("analysis"),
      security: outcome("security"),
      ...(state.measures ? { test: "done" } : {}),
      ...(state.draft ? { review: "done" } : {}),
    },
    summary: fx.report.summary,
    names: fx.report.pack.names,
    author: fx.report.pack.author ?? null,
    license: fx.report.pack.license ?? null,
    decision: state.published,
    tested: Boolean(state.measures),
    detected_at: "2026-10-16T08:00:00Z",
    published_at: state.published ? "2026-10-16T09:00:00Z" : null,
    ever_published: Boolean(state.published),
  });
  const detail = () => ({
    ...row(),
    pack,
    builtin: false,
    current: Boolean(state.published),
    report: fx.report,
    measures: state.measures,
    draft: state.draft,
    changes: null,
    elements: fx.elements,
  });
  const json = (route: Route, body: unknown, status = 200) => route.fulfill({ status, json: body });
  return {
    state,
    install: () =>
      page.route("**/api/v1/admin/visuals**", async (route) => {
        const url = new URL(route.request().url());
        const method = route.request().method();
        const path = url.pathname.replace("/api/v1/admin/visuals", "");
        if (path.startsWith("/files/")) {
          const file = path.split("/").slice(4).join("/");
          const body = readFileSync(resolve(ROOT, "examples/visual-packs", pack, file), "utf8");
          const type = file.endsWith(".css")
            ? "text/css"
            : file.endsWith(".js")
              ? "text/javascript"
              : "text/plain";
          return route.fulfill({ status: 200, contentType: type, body });
        }
        if (path === "" && method === "GET")
          return json(route, {
            inbox: "/data/visuals/inbox",
            packs: state.scanned
              ? [
                  {
                    id: pack,
                    names: fx.report.pack.names,
                    builtin: false,
                    socle: false,
                    source: { kind: "inbox" },
                    state: state.published ? "enabled" : "disabled",
                    current: state.published ? version : null,
                    remote: null,
                    update: false,
                    versions: [row()],
                    failures: 0,
                  },
                ]
              : [],
          });
        if (path === "/scan") {
          state.scanned = true;
          return json(route, { found: [{ pack, version, new: true }] });
        }
        if (path === "/contracts") return json(route, { contracts: [], widgets: [] });
        if (path === `/${pack}/${version}` && method === "GET") return json(route, detail());
        if (path === `/${pack}/${version}/measures`) {
          state.measures = {
            at: "2026-10-16T08:30:00Z",
            by: null,
            results: route.request().postDataJSON().results,
          };
          state.step = "tested";
          return json(route, detail());
        }
        if (path === `/${pack}/${version}/draft`) {
          state.draft = route.request().postDataJSON();
          state.step = "reviewed";
          return json(route, detail());
        }
        if (path === `/${pack}/${version}/publish`) {
          if (fx.report.summary.blocking)
            return json(route, { code: "ui.visual_pack_blocked", title: "Blocked" }, 422);
          state.published = { ...(state.draft ?? {}), ...route.request().postDataJSON() };
          state.step = "published";
          return json(route, { pack, version, products: {} });
        }
        return json(route, { code: "not_found", title: "Not found" }, 404);
      }),
  };
}

async function signIn(page: Page, width: number) {
  page.on("pageerror", (error) => console.log("pageerror:", error.message.slice(0, 300)));
  page.on("console", async (m) => {
    if (m.type() !== "error") return;
    const args = await Promise.all(
      m
        .args()
        .map((a) =>
          a.evaluate((v) => (v instanceof Error ? `${v.message}\n${v.stack}` : String(v))).catch(() => "?"),
        ),
    );
    console.log("console:", args.join(" ").slice(0, 800));
  });
  await page.setViewportSize({ width, height: 900 });
  await stubApi(page);
  await serveCatalogs(page);
  await page.route("**/api/v1/marketplace/products**", (route) => route.fulfill({ json: [] }));
  await page.route("**/api/v1/me/permissions", (route) =>
    route.fulfill({
      json: { permissions: ["users.self.manage", "visuals.manage", "admin.access"], roles: ["admin"] },
    }),
  );
  await page.goto("/");
  await page.getByLabel(/login/i).first().fill("alex");
  await page
    .getByLabel(/password/i)
    .first()
    .fill("correct horse battery");
  await page.keyboard.press("Enter");
  await expect(page.locator("#main-content")).toBeVisible();
}

const goTo = async (page: Page, path: string) => {
  await page.evaluate((to) => {
    window.history.pushState({}, "", to);
    window.dispatchEvent(new PopStateEvent("popstate"));
  }, path);
};

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
    const price = page.getByRole("spinbutton", { name: /Price — / }).first();
    await price.fill("1234");
    const script = page.getByRole("checkbox").first();
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
