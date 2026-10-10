import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import type { ReactElement } from "react";
import { createMemoryRouter, RouterProvider } from "react-router";
import { describe, expect, it } from "vitest";
import "../../../src/features/dashboard/widgets/builtin";
import "../../../src/features/gamification/widget";
import "../../../src/features/marketplace/widget";
import { widgetComponent } from "../../../src/features/dashboard/widgets/registry";

// 027 — the widgets redone after the review: quick access to the services (state and a direct link), the
// daily objectives (count and coins on one line, a reward badge per objective, done in the done colour)
// and the shop window (each product opens its sheet in the shop).

function show(key: string, data: unknown) {
  const Widget = widgetComponent(key);
  expect(Widget).toBeDefined();
  const Component = Widget as NonNullable<typeof Widget>;
  const element: ReactElement = <Component payload={{ state: "available", data } as never} config={{}} />;
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <RouterProvider router={createMemoryRouter([{ path: "/", element }])} />
    </QueryClientProvider>,
  );
}

describe("redesigned widgets", () => {
  it("links every service: outside in a new tab, else to its status page", () => {
    show("health.service_links", {
      items: [
        {
          id: "a",
          name: "Plex",
          connector: "plex",
          state: "operational",
          link: "https://plex.example",
          route: "/services/a",
        },
        { id: "b", name: "Sonarr", connector: "sonarr", state: "degraded", link: null, route: "/services/b" },
      ],
    });
    const plex = screen.getByRole("link", { name: /Plex/ });
    expect(plex.getAttribute("href")).toBe("https://plex.example");
    expect(plex.getAttribute("target")).toBe("_blank");
    expect(plex.getAttribute("rel")).toContain("noopener");
    expect(screen.getByRole("link", { name: /Sonarr/ }).getAttribute("href")).toBe("/services/b");
    expect(document.querySelector('[data-tone="warn"]')).not.toBeNull(); // degraded, also said in text
  });

  it("states the objectives done and the coins at stake, a done objective marked", () => {
    const quest = (key: string, done: boolean, coins: number) => ({
      key,
      kind: "daily",
      label: key,
      completed_at: done ? "2026-10-05T10:00:00Z" : null,
      steps: [{ current: done ? 1 : 0, target: 1 }],
      rewards: [{ value: "coins", amount: coins }],
    });
    show("gamification.daily_objectives", { items: [quest("Watch", true, 20), quest("Read", false, 30)] });
    const done = document.querySelector('.daily-objective[data-done="true"]');
    expect(done?.textContent).toContain("Watch");
    expect(document.querySelectorAll(".daily-objective")).toHaveLength(2);
    expect(document.querySelector(".daily-objectives__head")?.textContent).toContain("20 / 50");
  });

  it("opens a product of the shop window on its sheet", () => {
    show("marketplace.featured", {
      total: 12,
      items: [{ key: "theme_dune", name: "Dune", type: "theme", rarity: "epic", featured: true, price: 900 }],
    });
    expect(screen.getByRole("link", { name: /Dune/ }).getAttribute("href")).toBe(
      "/marketplace?product=theme_dune",
    );
  });
});
