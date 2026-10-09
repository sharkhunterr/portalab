import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import type { ReactElement } from "react";
import { createMemoryRouter, RouterProvider } from "react-router";
import { describe, expect, it } from "vitest";
import "../../../src/features/dashboard/widgets/builtin";
import "../../../src/features/dashboard/widgets/media";
import "../../../src/features/dashboard/widgets/discover";
import "../../../src/features/gamification/widget";
import { widgetComponent } from "../../../src/features/dashboard/widgets/registry";
import "../../../src/features/dashboard/widgets/skins";

// 027 — a widget on a single row shows its compact form (one line: the essentials), whatever look it
// wears; the daily objectives list the ones closest to done first.

function show(key: string, data: unknown, { compact = false, config = {} } = {}) {
  const Widget = widgetComponent(key);
  expect(Widget, key).toBeDefined();
  const Component = Widget as NonNullable<typeof Widget>;
  const element: ReactElement = (
    <Component payload={{ state: "available", data } as never} config={config} compact={compact} />
  );
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, enabled: false } } });
  return render(
    <QueryClientProvider client={client}>
      <RouterProvider router={createMemoryRouter([{ path: "/", element }])} />
    </QueryClientProvider>,
  );
}

const quest = (key: string, current: number, target: number, done = false) => ({
  key,
  kind: "daily",
  label: key,
  completed_at: done ? "2026-10-05T10:00:00Z" : null,
  steps: [{ current, target }],
  rewards: [{ value: "coins", amount: 10 }],
});
const objectives = [
  quest("Far", 1, 10),
  quest("Done", 3, 3, true),
  quest("Close", 4, 5),
  quest("Half", 1, 2),
];

describe("compact widgets", () => {
  it("daily objectives: the overall bar only on one row", () => {
    show("gamification.daily_objectives", { items: objectives }, { compact: true });
    expect(document.querySelector(".daily-objectives--compact")?.textContent).toContain("1/4");
    expect(screen.getByRole("progressbar").getAttribute("aria-valuenow")).toBe("25");
    expect(document.querySelectorAll(".daily-objective")).toHaveLength(0);
  });

  it("daily objectives: the closest to done first, the done ones last", () => {
    show("gamification.daily_objectives", { items: objectives });
    const order = [...document.querySelectorAll(".daily-objective__label")].map((n) => n.textContent);
    expect(order).toEqual(["Close", "Half", "Far", "Done"]);
  });

  it("my progression: a single row whatever the look", () => {
    show("gamification.progress", { level: 7 }, { compact: true, config: { style: "odometer" } });
    expect(document.querySelector(".widget-level--compact")?.textContent).toContain("7");
    expect(document.querySelector(".skin-odometer__sparks")).toBeNull();
  });

  it("services: the summary line alone", () => {
    const items = [{ id: "a", name: "Plex", connector: "plex", state: "operational", route: "/services/a" }];
    show("health.services_summary", { items, counts: { operational: 1 }, total: 1 }, { compact: true });
    expect(screen.getByText("The service is working")).toBeInTheDocument();
    expect(screen.queryByText("Plex")).toBeNull();
  });

  it("continue: the latest one only", () => {
    const card = (n: number) => ({
      id: `i${n}`,
      title: `Title ${n}`,
      kind: "movie",
      image_id: null,
      route: "/",
    });
    show("media.continue", { items: [card(1), card(2)] }, { compact: true });
    expect(screen.getByText("Title 1")).toBeInTheDocument();
    expect(screen.queryByText("Title 2")).toBeNull();
  });

  it("next releases: the soonest and the time left, on one line", () => {
    const at = new Date(Date.now() + 2 * 86_400_000 + 3_600_000).toISOString();
    show(
      "media.next_releases",
      { items: [{ id: "x", title: "Severance", at, route: "/" }] },
      { compact: true },
    );
    expect(screen.getByText("Severance")).toBeInTheDocument();
    expect(screen.getByRole("timer").textContent).toMatch(/^2d 0[01]:\d\d:\d\d$/);
  });
});
