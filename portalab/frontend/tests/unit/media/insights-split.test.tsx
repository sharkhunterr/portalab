import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router";
import { describe, expect, it, vi } from "vitest";

// Issue 484 — the activity chart of a household or of the server, by kind or by person: a switch at its
// top-right, the legend then naming each member (« You », « Other members », « Unattributed » apart).

const fake = vi.hoisted(() => ({
  handler: (_: Request): Response | Promise<Response> => new Response(null, { status: 404 }),
}));
vi.mock("../../../src/api/client", async (importOriginal) => {
  const { installFakeApi } = await import("../../support/fake-api");
  const installed = installFakeApi();
  Object.defineProperty(installed, "handler", { get: () => fake.handler });
  return importOriginal();
});

import InsightsPage from "../../../src/features/media/insights/InsightsPage";
import { json } from "../../support/fake-api";

globalThis.ResizeObserver ??= class {
  observe() {}
  unobserve() {}
  disconnect() {}
} as unknown as typeof ResizeObserver;

const insights = (members?: unknown) => ({
  period: { key: "30d", start: null, end: "2026-11-17" },
  scope: "all",
  category: "all",
  manager: true,
  totals: { plays: 3, completed: 1, seconds: 7200, active_days: 1, works: 2, members: 2 },
  previous: null,
  by_kind: [{ kind: "movie", plays: 3, seconds: 7200 }],
  timeline: {
    unit: "day",
    points: [
      {
        date: "2026-11-16",
        seconds: { movie: 5400, episode: 1800 },
        plays: 3,
        plays_by_kind: { movie: 2, episode: 1 },
        ...(members
          ? { members: { u1: { seconds: 5400, plays: 2 }, unattributed: { seconds: 1800, plays: 1 } } }
          : {}),
      },
    ],
    ...(members ? { members } : {}),
  },
  heatmap: [],
  top_works: [],
  genres: [],
  people: [],
  decades: [],
  records: { longest: null, busiest_day: null, best_streak: 0, completed: 1, first_at: null },
  box_office: null,
  platforms: null,
  recent: null,
  members: null,
  requests: null,
  locked: [],
});

function show(body: unknown, at = "/?scope=all") {
  fake.handler = (request) => {
    const path = new URL(request.url).pathname;
    if (path === "/api/v1/media/insights") return json(200, body);
    if (path === "/api/v1/media/insights/categories") return json(200, { categories: ["all"] });
    if (path === "/api/v1/me/media/insights/locked") return json(200, { locked: [] });
    if (path === "/api/v1/me") return json(200, { household_profiles: 0 });
    return json(404, {});
  };
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <RouterProvider
        router={createMemoryRouter([{ path: "/", element: <InsightsPage /> }], { initialEntries: [at] })}
      />
    </QueryClientProvider>,
  );
}

describe("the activity chart by person (issue 484)", () => {
  it("switches from kinds to members, named", async () => {
    show(
      insights([
        { key: "u1", name: "Zoé", me: true },
        { key: "unattributed", name: null, me: false },
      ]),
    );
    const split = await screen.findByRole("group", { name: "Split" });
    const legend = () => document.querySelector(".insights-legend") as HTMLElement;
    expect(within(legend()).getByText("Films")).toBeTruthy();
    fireEvent.click(within(split).getByRole("radio", { name: /By person/ }));
    await waitFor(() => expect(within(legend()).getByText("Zoé")).toBeTruthy());
    expect(within(legend()).getByText("Unattributed")).toBeTruthy();
    expect(within(legend()).queryByText("Films")).toBeNull();
  });

  it("offers no split for one's own figures", async () => {
    show(insights(), "/");
    await screen.findByRole("group", { name: "Show" });
    expect(screen.queryByRole("group", { name: "Split" })).toBeNull();
  });
});
