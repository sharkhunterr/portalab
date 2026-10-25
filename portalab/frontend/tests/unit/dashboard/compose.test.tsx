import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, within } from "@testing-library/react";
import axe from "axe-core";
import { MemoryRouter } from "react-router";
import { describe, expect, it, vi } from "vitest";

// Issue 250 — the default dashboard composed by the administrator with the members' editor: the widgets
// drawn on the grid, each one's lock changed from its frame, a widget placed, another switched off, a phone
// following the computer until arranged — and one save sending it all.

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
import DashboardAdmin, { cellsOf } from "../../../src/features/dashboard/admin/DashboardAdmin";
import { json } from "../../support/fake-api";

const meta = (title: string) => ({
  title_key: title,
  description_key: null,
  icon: null,
  component_id: null,
  template: "stat",
  refresh_mode: "on_view",
  refresh_interval_s: null,
  min_w: 2,
  min_h: 1,
  max_w: 12,
  max_h: 4,
  multiple: false,
  config_schema: { type: "object", properties: {} },
});

describe("default dashboard composer", () => {
  it("derives a phone from the computer until the phone has places of its own", () => {
    const items = [
      { widget_key: "a", x: 0, y: 0, w: 6, h: 2, config: {}, lock: "free" as const },
      { widget_key: "b", x: 6, y: 0, w: 6, h: 2, config: {}, lock: "free" as const },
    ];
    expect([...cellsOf(items, "phone").values()]).toEqual([
      { x: 0, y: 0, w: 4, h: 2 },
      { x: 0, y: 2, w: 4, h: 2 },
    ]);
    const own = [{ ...items[0], phone: { x: 0, y: 5, w: 4, h: 2 } }, items[1]] as typeof items;
    expect(cellsOf(own, "phone").get("a")).toEqual({ x: 0, y: 5, w: 4, h: 2 });
  });

  it("changes a widget's lock, places another, switches one off and saves it all", async () => {
    const sent: unknown[] = [];
    const composition = {
      items: [{ widget_key: "t.news", x: 0, y: 0, w: 6, h: 2, config: {}, lock: "free" }],
      disabled: [],
    };
    fake.handler = async (request) => {
      const path = new URL(request.url).pathname;
      if (path === "/api/v1/admin/dashboard/composition" && request.method === "PUT") {
        const body = await request.json();
        sent.push(body);
        return json(200, body);
      }
      if (path === "/api/v1/admin/dashboard/composition") return json(200, composition);
      if (path === "/api/v1/admin/dashboard/policies")
        return json(200, {
          policies: {},
          starter: [],
          widgets: [
            { key: "t.news", title_key: "News", size: { default: { w: 6, h: 2 } } },
            { key: "t.radio", title_key: "Radio", size: { default: { w: 4, h: 2 } } },
            { key: "t.shop", title_key: "Shop", size: { default: { w: 4, h: 2 } } },
          ],
        });
      if (path === "/api/v1/dashboard/catalog")
        return json(200, [
          { key: "t.news", locked: false, placed: false, product: null, widget: meta("News") },
          { key: "t.radio", locked: false, placed: false, product: null, widget: meta("Radio") },
        ]);
      if (path === "/api/v1/dashboard/locked-options") return json(200, { locked: [] });
      return json(200, {
        state: "available",
        as_of: null,
        stale_after_s: null,
        data: { value: 1, label: "One" },
        partial_reasons: [],
        config_invalid: false,
      });
    };
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const { container } = render(
      <QueryClientProvider client={client}>
        <AnnounceProvider>
          <MemoryRouter>
            <DashboardAdmin />
          </MemoryRouter>
        </AnnounceProvider>
      </QueryClientProvider>,
    );
    const toolbar = await screen.findByRole("toolbar", { name: "News" });
    const lock = within(toolbar).getByRole("button", { name: /Lock: Free/ });
    fireEvent.click(lock);
    fireEvent.click(within(toolbar).getByRole("button", { name: /Lock: Always there/ }));
    expect(within(toolbar).getByRole("button", { name: /Lock: Locked/ })).toBeInTheDocument();
    // another widget placed from the list of the others, a third switched off for everyone
    const others = screen
      .getByRole("heading", { name: "The other widgets" })
      .closest("section") as HTMLElement;
    fireEvent.click(within(others).getAllByRole("button", { name: /Place/ })[0] as HTMLElement);
    expect(await screen.findByRole("toolbar", { name: "Radio" })).toBeInTheDocument();
    fireEvent.click(within(others).getByRole("checkbox", { name: "Switched off for everyone" }));
    // the phone follows the computer
    fireEvent.click(screen.getByRole("button", { name: /Phone|Mobile/ }));
    expect(screen.getByText(/follows the computer's arrangement/)).toBeInTheDocument();
    const results = await axe.run(container, { rules: { "color-contrast": { enabled: false } } });
    expect(results.violations.map((v) => v.id)).toEqual([]);
    fireEvent.click(screen.getAllByRole("button", { name: /^Save$/ })[0] as HTMLElement);
    await vi.waitFor(() => expect(sent).toHaveLength(1));
    expect(sent[0]).toEqual({
      items: [
        { widget_key: "t.news", x: 0, y: 0, w: 6, h: 2, config: {}, lock: "locked" },
        { widget_key: "t.radio", x: 6, y: 0, w: 4, h: 2, config: {}, lock: "free" },
      ],
      disabled: ["t.shop"],
    });
    expect(await screen.findByText("Saved.")).toBeInTheDocument();
  }, 20_000);
});
