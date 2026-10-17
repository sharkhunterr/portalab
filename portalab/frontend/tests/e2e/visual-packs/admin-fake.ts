import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { expect, type Page, type Route } from "@playwright/test";
import { stubApi } from "../../a11y/support";
import { serveCatalogs } from "./support";

/** 028: the Admin API of visual packs faked for one pack (its report the real analysis's), a signed-in
 * administrator, in-app navigation — shared by the workflow's journeys and its accessibility sweep. */
const HERE = dirname(fileURLToPath(import.meta.url));
const ROOT = resolve(HERE, "../../../..");
export const fixture = (name: string) =>
  JSON.parse(readFileSync(resolve(HERE, "fixtures", `${name}.json`), "utf8"));

type Step = "analysed" | "tested" | "reviewed" | "published";

export function fakeAdmin(page: Page, fx: { report: Record<string, any>; elements: unknown[] }) {
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
          let body: string;
          try {
            body = readFileSync(resolve(ROOT, "examples/visual-packs", pack, file), "utf8");
          } catch {
            return route.fulfill({ status: 404, body: "" });
          }
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

export async function signIn(page: Page, width: number) {
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

export const goTo = async (page: Page, path: string) => {
  await page.evaluate((to) => {
    window.history.pushState({}, "", to);
    window.dispatchEvent(new PopStateEvent("popstate"));
  }, path);
};
