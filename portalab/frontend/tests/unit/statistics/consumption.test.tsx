import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router";
import { describe, expect, it, vi } from "vitest";

// 017 T014/T027 — the user consumes administrator-defined statistics: period changes refetch in place; only
// hideable statistics offer "Hide"; there is no chart/query builder; every state renders through
// FunctionalState (locked shows only the hint, insufficient data, stale with a date); each chart has a text
// summary and a data table alternative.

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
import { StatisticsPage } from "../../../src/features/statistics/StatisticsPage";
import { json } from "../../support/fake-api";

globalThis.ResizeObserver ??= class {
  observe() {}
  unobserve() {}
  disconnect() {}
} as unknown as typeof ResizeObserver;

const entry = (key: string, extra: Record<string, unknown> = {}) => ({
  key,
  title_key: key,
  description_key: null,
  domain: "media",
  scope: "community",
  viz: "line",
  hideable: true,
  locked: false,
  unlock_hint: null,
  period_options: ["day", "week", "month"],
  hidden: false,
  ...extra,
});

const result = (key: string, extra: Record<string, unknown> = {}) => ({
  key,
  state: "available",
  definition_version: 1,
  as_of: "2026-10-05T10:00:00Z",
  value: 42,
  series: [
    { day: "2026-10-04", value: 20 },
    { day: "2026-10-05", value: 22 },
  ],
  breakdown: [],
  trend: { delta: 2, direction: "up", previous_value: 40, percent: 5 },
  unlock_hint: null,
  source_states: {},
  period_start: "2026-09-06",
  period_end: "2026-10-05",
  ...extra,
});

function setup() {
  const requests: string[] = [];
  const saved: unknown[] = [];
  fake.handler = async (request) => {
    const url = new URL(request.url);
    requests.push(`${request.method} ${url.pathname}${url.search}`);
    if (url.pathname === "/api/v1/statistics/catalog")
      return json(200, [
        entry("media.minutes"),
        entry("media.mandatory", { hideable: false }),
        entry("media.locked", { locked: true, unlock_hint: "statistics:unlock.level_at_least" }),
        entry("media.small"),
        entry("media.old"),
      ]);
    if (url.pathname === "/api/v1/me/statistics/preferences") {
      if (request.method === "PUT") saved.push(await request.json());
      return json(200, { hidden: [] });
    }
    const key = decodeURIComponent(url.pathname.split("/").pop() ?? "");
    if (key === "media.small")
      return json(200, result(key, { state: "insufficient_data", value: null, series: [] }));
    if (key === "media.old") return json(200, result(key, { state: "stale" }));
    return json(200, result(key));
  };
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <AnnounceProvider>
        <RouterProvider router={createMemoryRouter([{ path: "/", element: <StatisticsPage /> }])} />
      </AnnounceProvider>
    </QueryClientProvider>,
  );
  return { requests, saved };
}

const card = (key: string) => document.querySelector(`[data-statistic="${key}"]`) as HTMLElement;

describe("statistics page", () => {
  it("renders states, summaries and table alternatives", async () => {
    const { requests } = setup();
    await waitFor(() => expect(within(card("media.minutes")).getByText("media.minutes: 42")).toBeTruthy());
    expect(within(card("media.minutes")).getByText(/Up 2/)).toBeTruthy();
    const toggle = within(card("media.minutes")).getByRole("button", { name: "Show the data table" });
    fireEvent.click(toggle);
    expect(within(card("media.minutes")).getAllByRole("row").length).toBe(3);
    expect(
      within(card("media.locked")).getByText("Reach a higher level to unlock this statistic."),
    ).toBeTruthy();
    expect(requests.some((r) => r.includes("/statistics/media.locked"))).toBe(false); // nothing requested while locked
    await waitFor(() => expect(card("media.small").querySelector('[data-state="no-data"]')).toBeTruthy());
    await waitFor(() => expect(card("media.old").querySelector('[data-state="stale"]')).toBeTruthy());
    expect(screen.queryByText(/create|query builder/i)).toBeNull();
  });

  it("changes the period in place and hides only hideable statistics", async () => {
    const { requests, saved } = setup();
    await screen.findAllByText("media.minutes: 42");
    fireEvent.change(screen.getByLabelText("Period"), { target: { value: "week" } });
    await waitFor(() =>
      expect(requests.some((r) => r.includes("/statistics/media.minutes?period=week"))).toBe(true),
    );
    expect(within(card("media.mandatory")).queryByRole("button", { name: "Hide" })).toBeNull();
    fireEvent.click(within(card("media.minutes")).getByRole("button", { name: "Hide" }));
    await waitFor(() => expect(saved).toEqual([{ hidden: ["media.minutes"] }]));
  });
});
