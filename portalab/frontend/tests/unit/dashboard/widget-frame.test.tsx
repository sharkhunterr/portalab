import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router";
import { describe, expect, it, vi } from "vitest";

// 009 T010/T015/T019 — each widget frame fetches on its own; a crashing widget shows an error state in its
// own frame while siblings render; every state renders through FunctionalState; edit controls are plain
// buttons sending If-Match; locked/mandatory actions are disabled; a version conflict reloads and announces;
// no dashboard code styles functional states itself.

const fake = vi.hoisted(() => ({
  handler: (_: Request): Response | Promise<Response> => new Response(null),
}));
vi.mock("../../../src/api/client", async (importOriginal) => {
  const { installFakeApi } = await import("../../support/fake-api");
  const installed = installFakeApi();
  Object.defineProperty(installed, "handler", { get: () => fake.handler });
  return importOriginal();
});

import { AnnounceProvider } from "../../../src/design-system/a11y/Announce";
import { DashboardPage } from "../../../src/features/dashboard/DashboardPage";
import { registerWidgetComponent } from "../../../src/features/dashboard/widgets/registry";
import { json } from "../../support/fake-api";

const meta = (overrides: Record<string, unknown> = {}) => ({
  title_key: "dashboard:widget.welcome.title",
  description_key: null,
  icon: null,
  component_id: null,
  template: "stat",
  refresh_mode: "on_view",
  refresh_interval_s: null,
  min_w: 2,
  min_h: 1,
  max_w: 8,
  max_h: 4,
  multiple: false,
  config_schema: { type: "object", properties: {} },
  ...overrides,
});

const instance = (key: string, position: number, overrides: Record<string, unknown> = {}) => ({
  id: `00000000-0000-7000-8000-00000000000${position}`,
  widget_key: key,
  status: "active",
  position,
  w: 4,
  h: 2,
  config: {},
  policy: "free",
  locked: false,
  mandatory: false,
  removable: true,
  hideable: true,
  available: true,
  ...overrides,
  widget: meta((overrides.widget as Record<string, unknown>) ?? {}),
});

const PAYLOADS: Record<string, unknown> = {
  "t.ok": {
    state: "available",
    as_of: null,
    stale_after_s: null,
    data: { value: 42, label: "Answers" },
    partial_reasons: [],
    config_invalid: false,
  },
  "t.down": {
    state: "unavailable",
    as_of: null,
    stale_after_s: null,
    data: null,
    partial_reasons: [],
    config_invalid: false,
  },
  "t.crash": {
    state: "available",
    as_of: null,
    stale_after_s: null,
    data: {},
    partial_reasons: [],
    config_invalid: false,
  },
  "t.partial": {
    state: "partial",
    as_of: "2026-10-05T10:00:00Z",
    stale_after_s: null,
    data: { value: 1 },
    partial_reasons: ["one source down"],
    config_invalid: false,
  },
  "t.secret": {
    state: "unauthorized",
    as_of: null,
    stale_after_s: null,
    data: null,
    partial_reasons: [],
    config_invalid: false,
  },
};

registerWidgetComponent("test.crash", () => {
  throw new Error("widget bug");
});

function setup(dashboard: unknown, onWrite?: (request: Request) => Response | Promise<Response>) {
  const requests: string[] = [];
  fake.handler = (request) => {
    const url = new URL(request.url);
    requests.push(`${request.method} ${url.pathname}`);
    if (url.pathname === "/api/v1/dashboard") return json(200, dashboard);
    if (url.pathname === "/api/v1/dashboard/since-last-login")
      return json(200, { since: "2026-10-01T00:00:00Z", items: [], unavailable: [] });
    const widget = /^\/api\/v1\/widgets\/([^/]+)\/data$/.exec(url.pathname);
    if (widget) return json(200, PAYLOADS[decodeURIComponent(widget[1] as string)]);
    if (onWrite) return onWrite(request);
    return json(404, {});
  };
  const router = createMemoryRouter([{ path: "/", element: <DashboardPage live={false} /> }]);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <AnnounceProvider>
        <RouterProvider router={router} />
      </AnnounceProvider>
    </QueryClientProvider>,
  );
  return { requests };
}

const frame = (name: string) => screen.getByRole("heading", { name }).closest("section") as HTMLElement;

describe("widget frames", () => {
  it("load independently and contain their own failures", async () => {
    const titles = { ok: "Answers", down: "Down", crash: "Crashy", partial: "Partial", secret: "Secret" };
    const { requests } = setup({
      layout_version: 3,
      instances: [
        instance("t.ok", 0, { widget: { title_key: titles.ok } }),
        instance("t.down", 1, { widget: { title_key: titles.down } }),
        instance("t.crash", 2, { widget: { title_key: titles.crash, component_id: "test.crash" } }),
        instance("t.partial", 3, { widget: { title_key: titles.partial } }),
        instance("t.secret", 4, { widget: { title_key: titles.secret } }),
        instance("t.gone", 5, { available: false, widget: { title_key: "Gone" } }),
      ],
    });
    await screen.findByText("42");
    await waitFor(() =>
      expect(within(frame(titles.crash)).getByText(/could not be loaded|error/i)).toBeTruthy(),
    );
    expect(within(frame(titles.down)).getByText(/not available|unavailable/i)).toBeTruthy();
    expect(within(frame(titles.partial)).getByText(/one source down/)).toBeTruthy();
    expect(frame(titles.secret).querySelector('[data-state="unauthorized"]')).toBeTruthy();
    expect(within(frame("Gone")).getByText("This widget is no longer available.")).toBeTruthy();
    for (const key of ["t.ok", "t.down", "t.crash", "t.partial", "t.secret"])
      expect(requests).toContain(`GET /api/v1/widgets/${key}/data`);
    expect(requests).not.toContain("GET /api/v1/widgets/t.gone/data");
  });
});

describe("edit mode", () => {
  it("uses plain buttons with If-Match, respects policies and reloads on conflict", async () => {
    const writes: Array<{ method: string; path: string; ifMatch: string | null; body: unknown }> = [];
    let conflict = false;
    setup(
      {
        layout_version: 7,
        instances: [
          instance("t.ok", 0, { widget: { title_key: "First" } }),
          instance("t.partial", 1, {
            locked: true,
            mandatory: true,
            removable: false,
            hideable: false,
            widget: { title_key: "Locked" },
          }),
        ],
      },
      async (request) => {
        writes.push({
          method: request.method,
          path: new URL(request.url).pathname,
          ifMatch: request.headers.get("If-Match"),
          body: request.method === "PATCH" ? await request.json() : null,
        });
        return conflict
          ? json(409, { code: "dashboard.version_conflict", title: "Conflict" })
          : json(200, { layout_version: 8, id: null });
      },
    );
    await screen.findByText("42");
    fireEvent.click(screen.getByRole("button", { name: "Customize" }));
    const first = within(frame("First"));
    expect((first.getByRole("button", { name: "Move up" }) as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(first.getByRole("button", { name: "Move down" }));
    await waitFor(() =>
      expect(writes[0]).toMatchObject({ method: "PATCH", ifMatch: "7", body: { position: 1 } }),
    );
    fireEvent.click(first.getByRole("button", { name: "Wider" }));
    await waitFor(() => expect(writes[1]?.body).toEqual({ w: 5, h: 2 }));
    const locked = within(frame("Locked"));
    for (const name of ["Move up", "Wider", "Hide", "Remove"])
      expect((locked.getByRole("button", { name }) as HTMLButtonElement).disabled).toBe(true);
    conflict = true;
    fireEvent.click(first.getByRole("button", { name: "Hide" }));
    expect(await screen.findByText(/changed on another device/)).toBeTruthy();
  });
});

describe("state styling", () => {
  it("dashboard code never styles functional states itself", () => {
    const root = join(__dirname, "../../../src/features/dashboard");
    const files: string[] = [];
    const walk = (dir: string) => {
      for (const entry of readdirSync(dir, { withFileTypes: true })) {
        if (entry.isDirectory()) walk(join(dir, entry.name));
        else if (/\.(css|tsx?)$/.test(entry.name)) files.push(join(dir, entry.name));
      }
    };
    walk(root);
    for (const file of files) {
      const source = readFileSync(file, "utf8");
      expect(source, file).not.toMatch(/--state-|functional-state--|\[data-state[=\]]/);
    }
  });
});
