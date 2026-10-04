import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router";
import { describe, expect, it, vi } from "vitest";

// 009 T014 — every widget state, under the light, dark and high-contrast themes, keeps its meaning with a
// non-color cue (text + icon) and the same role; critical information (the state label) stays visible.

const fake = vi.hoisted(() => ({
  handler: (_: Request): Response | Promise<Response> => new Response(null),
}));
vi.mock("../../src/api/client", async (importOriginal) => {
  const { installFakeApi } = await import("../support/fake-api");
  const installed = installFakeApi();
  Object.defineProperty(installed, "handler", { get: () => fake.handler });
  return importOriginal();
});

import { PreferencesProvider } from "../../src/design-system/a11y/PreferencesProvider";
import { BUILTIN_THEMES } from "../../src/design-system/themes/builtin";
import { ThemeProvider } from "../../src/design-system/themes/ThemeProvider";
import { WidgetFrame } from "../../src/features/dashboard/frame/WidgetFrame";
import { json } from "../support/fake-api";

const STATES = ["unavailable", "error", "unauthorized", "no-data", "partial", "stale"] as const;

function frame(state: string) {
  return {
    id: "00000000-0000-7000-8000-000000000001",
    widget_key: `t.${state}`,
    status: "active" as const,
    position: 0,
    x: 0,
    y: 0,
    w: 4,
    h: 2,
    config: {},
    policy: "free",
    locked: false,
    mandatory: false,
    removable: true,
    hideable: true,
    available: true,
    widget: {
      title_key: `Widget ${state}`,
      description_key: null,
      icon: null,
      component_id: null,
      template: "stat",
      refresh_mode: "on_view",
      refresh_interval_s: null,
      min_w: 1,
      min_h: 1,
      max_w: 12,
      max_h: 6,
      multiple: false,
      config_schema: {},
    },
  };
}

async function renderAll(theme: string) {
  fake.handler = (request) => {
    const key = decodeURIComponent(/widgets\/([^/]+)\/data/.exec(new URL(request.url).pathname)?.[1] ?? "");
    const state = key.slice(2);
    return json(200, {
      state,
      as_of: "2026-10-05T10:00:00Z",
      stale_after_s: 60,
      data: { value: 1 },
      partial_reasons: state === "partial" ? ["one source down"] : [],
      config_invalid: false,
    });
  };
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const router = createMemoryRouter([
    {
      path: "/",
      element: (
        <>
          {STATES.map((state) => (
            <WidgetFrame key={state} instance={frame(state)} />
          ))}
        </>
      ),
    },
  ]);
  const view = render(
    <PreferencesProvider initial={{ theme }} policy={{ allowedThemes: ["light", "dark", "high-contrast"] }}>
      <ThemeProvider themes={BUILTIN_THEMES}>
        <QueryClientProvider client={client}>
          <RouterProvider router={router} />
        </QueryClientProvider>
      </ThemeProvider>
    </PreferencesProvider>,
  );
  await screen.findByText(/one source down/);
  await vi.waitFor(() =>
    expect(
      view.container.querySelectorAll("[data-state]:not([data-state=loading])").length,
    ).toBeGreaterThanOrEqual(STATES.length),
  );
  const rows = STATES.map((state) => {
    const element = view.container.querySelector(
      `[data-widget="t.${state}"] [data-state="${state}"]`,
    ) as HTMLElement;
    return {
      state,
      role: element?.getAttribute("role"),
      text: element?.textContent?.trim(),
      icon: element?.querySelector("svg")?.getAttribute("data-icon"),
    };
  });
  view.unmount();
  return rows;
}

describe("widget states across themes", () => {
  it("keep a text and icon cue and the same semantics in every theme", async () => {
    const light = await renderAll("light");
    for (const row of light) {
      expect(row.text, row.state).toBeTruthy();
      expect(row.icon, row.state).toBeTruthy();
    }
    for (const theme of ["dark", "high-contrast"]) {
      const rows = await renderAll(theme);
      expect(rows.map((r) => [r.state, r.role, r.text])).toEqual(light.map((r) => [r.state, r.role, r.text]));
      expect(rows.every((r) => Boolean(r.icon))).toBe(true);
    }
  });
});
