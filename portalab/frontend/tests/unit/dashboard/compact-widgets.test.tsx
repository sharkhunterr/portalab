import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import type { ReactElement } from "react";
import { createMemoryRouter, RouterProvider } from "react-router";
import { describe, expect, it } from "vitest";
import "../../../src/features/dashboard/widgets/builtin";
import "../../../src/features/dashboard/widgets/media";
import "../../../src/features/dashboard/widgets/leaving";
import "../../../src/features/dashboard/widgets/discover";
import "../../../src/features/gamification/widget";
import "../../../src/features/dashboard/widgets/calendar";
import "../../../src/features/dashboard/widgets/service-status";
import "../../../src/features/campaigns/widget";
import "../../../src/features/marketplace/widget";
import "../../../src/features/support/incidents/widget";
import { widgetComponent } from "../../../src/features/dashboard/widgets/registry";
import "../../../src/features/dashboard/widgets/skins";

// 027 — a widget on a single row shows its compact form (one line: the essentials), whatever look it
// wears; the daily objectives list the ones closest to done first.

function show(key: string, data: unknown, { compact = false, config = {} } = {}) {
  const Widget = widgetComponent(key);
  expect(Widget, key).toBeDefined();
  const Component = Widget as NonNullable<typeof Widget>;
  const element: ReactElement = (
    <Component
      payload={{ state: "available", data } as never}
      config={config}
      compact={compact}
      rows={compact ? 1 : undefined}
    />
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

  it("posters, the poster wall: a strip of posters", () => {
    const card = (n: number) => ({
      id: `i${n}`,
      title: `Title ${n}`,
      image_id: `img${n}`,
      route: `/media/i${n}`,
    });
    show("media.posters", { items: [card(1), card(2), card(3)] }, { compact: true });
    expect(document.querySelectorAll(".poster-strip li")).toHaveLength(3);
    expect(screen.getByRole("link", { name: "Title 2" }).getAttribute("href")).toBe("/media/i2");
  });

  it("statistics: the headline, the context and the trend", () => {
    const data = {
      scope: "me",
      period: "30d",
      metric: "plays",
      totals: { plays: 10, seconds: 3600, works: 3 },
      previous: { plays: 20, seconds: 7200 },
      series: [],
      top_works: [],
    };
    show("media.stats", data, { compact: true });
    expect(document.querySelector(".compact-line strong")?.textContent).toBe("10");
    expect(document.querySelector(".widget-media-stats__trend")?.getAttribute("data-trend")).toBe("down");
  });

  it("the calendar: this week, today marked", () => {
    show(
      "calendar.month",
      {
        month: "2026-10-01",
        today: "2026-10-09",
        entries: [{ title: "Night", kind: "event", route: "/", date: "2026-10-09", end: "2026-10-09" }],
        upcoming: [],
      },
      { compact: true },
    );
    const days = document.querySelectorAll(".cal-week__day");
    expect(days).toHaveLength(7);
    const today = document.querySelector(".cal-week__day[data-today]");
    expect(today?.textContent).toContain("9");
    expect(today?.querySelectorAll(".cal-week__dots span")).toHaveLength(1);
  });

  it("incidents: all is well, or the incident going on", () => {
    show("support.incidents", { open: 0, items: [] }, { compact: true });
    expect(document.querySelector(".incidents-widget--compact[data-ok]")).not.toBeNull();
  });

  it("the campaign: what it boosts and how long is left", () => {
    const ends = new Date(Date.now() + 3 * 86_400_000).toISOString();
    show(
      "campaigns.active",
      {
        items: [
          {
            key: "autumn",
            title: "Autumn festival",
            route: "/campaigns/autumn",
            ends_at: ends,
            description: "",
            boosts: [{ value: "xp", factor: 1.5 }],
          },
        ],
      },
      { compact: true },
    );
    expect(screen.getByText("Autumn festival")).toBeInTheDocument();
    expect(screen.getByText("×1.5 XP")).toBeInTheDocument();
  });

  it("the shop window: its first product and its price", () => {
    show(
      "marketplace.featured",
      { items: [{ key: "theme_dune", name: "Dune", type: "theme", price: 900 }] },
      { compact: true },
    );
    expect(screen.getByRole("link", { name: /Dune/ }).getAttribute("href")).toBe(
      "/marketplace?product=theme_dune",
    );
  });
});

describe("service status", () => {
  const item = {
    id: "s1",
    name: "Plex",
    connector: "plex",
    state: "operational",
    availability: 0.996,
    link: "https://plex.example",
    route: "/services/s1",
  };

  it("shows one service as on the services page", () => {
    show("health.service_status", { item });
    expect(screen.getByText("Plex")).toBeInTheDocument();
    expect(screen.getByText(/99.6% available/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Open/ }).getAttribute("href")).toBe("https://plex.example");
  });

  it("on a single row: its name and state", () => {
    show("health.service_status", { item }, { compact: true });
    expect(screen.getByRole("link", { name: /Plex/ }).getAttribute("href")).toBe("/services/s1");
  });

  it("leaving soon: the cards of the other rows of posters, the day it goes as a badge on the poster", () => {
    const soon = new Date(Date.now() + 3 * 86_400_000).toISOString();
    const items = [
      {
        id: "a",
        title: "Heat",
        kind: "movie",
        delete_at: soon,
        collection: "Old",
        image_id: null,
        route: "/media/a",
      },
      {
        id: "b",
        title: "Lost",
        kind: "season",
        delete_at: null,
        collection: "Old",
        image_id: null,
        route: null,
      },
    ];
    show("media.leaving", { items });
    const cards = Array.from(document.querySelectorAll(".widget-posters > li"));
    expect(cards.map((li) => li.querySelector(".widget-posters__title")?.textContent)).toEqual([
      "Heat",
      "Lost",
    ]);
    const badge = cards[0]?.querySelector('.discover-status[data-status="leaving"]');
    expect(badge?.textContent).toContain("in 3 days"); // contracted to its icon on screen, read out whole
    expect(badge?.getAttribute("title")).toContain("in 3 days");
    expect(cards[1]?.querySelector(".widget-posters__art")?.textContent).toBe("leaving soon");
    show("media.leaving", { items }, { compact: true });
    expect(document.querySelector(".poster-strip")).not.toBeNull();
  });
});
