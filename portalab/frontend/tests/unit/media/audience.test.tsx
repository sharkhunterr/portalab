import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { createMemoryRouter, RouterProvider } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

// issue 222 — « My requests »: the audience of my requests (a number, never who), my most watched requests,
// the requesters' podiums (named as on the leaderboards, else « A member ») and the audience in depth.

const fake = vi.hoisted(() => ({
  handler: (_: Request): Response | Promise<Response> => new Response(null),
}));
vi.mock("../../../src/api/client", async (importOriginal) => {
  const { installFakeApi } = await import("../../support/fake-api");
  const installed = installFakeApi();
  Object.defineProperty(installed, "handler", { get: () => fake.handler });
  return importOriginal();
});

import { AudienceSummary, AudienceTitles, Leaders } from "../../../src/features/media/requests/Audience";
import { AudienceDepth } from "../../../src/features/media/requests/AudienceDepth";
import type { RequestInsights } from "../../../src/features/media/requests/api";
import { json } from "../../support/fake-api";

function show(element: ReactNode) {
  fake.handler = async () => json(200, {});
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const router = createMemoryRouter([{ path: "/", element }], { initialEntries: ["/"] });
  return render(
    <QueryClientProvider client={client}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
}

const rates = { available: 4, seen_rate: 0.5, viewers_per_request: 1.5 };
const depth: NonNullable<RequestInsights["audience_depth"]> = {
  reactivity: {
    median_hours: 30,
    buckets: [
      { key: "hour", count: 1 },
      { key: "day", count: 2 },
    ],
    waiting: 2,
    fastest: [{ title: "Dune", hours: 0.5 }],
    slowest: [{ title: "Heat", hours: 400 }],
  },
  genres: { mine: [{ name: "Sci-Fi", viewers: 6, requests: 2 }], server: [] },
  kinds: { movie: { ...rates, requests: 4, plays: 9 }, series: { ...rates, requests: 0, plays: 0 } },
  versus: { mine: rates, server: { available: 20, seen_rate: 0.25, viewers_per_request: 0.8 } },
  late_share: 0.2,
  over_time: { unit: "month", points: [{ date: "2026-09-01", plays: 4 }] },
};

afterEach(cleanup);

describe("issue 222 — the audience of my requests", () => {
  it("shows the totals, the most watched requests and the podiums, never who watched", async () => {
    show(
      <>
        <AudienceSummary data={{ requested: 4, seen: 2, viewers: 3, plays: 9 }} />
        <AudienceTitles
          data={{
            items: [{ id: "d", title: "Dune", kind: "movie", viewers: 3, plays: 5 }],
            position: 2,
            total: 5,
          }}
        />
        <Leaders
          data={{
            requests: [
              { rank: 1, me: false, name: null, value: 9, requests: 9 },
              { rank: 2, me: true, name: null, value: 4, requests: 4 },
            ],
            viewers: [{ rank: 1, me: false, name: "Thibaut", value: 7, requests: 3 }],
            per_request: [],
          }}
        />
      </>,
    );
    expect(await screen.findByText("3 members watched your requests")).toBeTruthy();
    expect(screen.getByText("Dune")).toBeTruthy();
    expect(screen.getByText(/2nd requester by audience out of 5/)).toBeTruthy();
    expect(screen.getByText("A member")).toBeTruthy();
    expect(screen.getByText("You")).toBeTruthy();
    expect(screen.getByText("Thibaut")).toBeTruthy();
  });

  it("shows the audience in depth: reactivity, against the server, genres, over time", async () => {
    show(<AudienceDepth data={depth} />);
    expect(await screen.findByText("Reactivity")).toBeTruthy();
    expect(screen.getByText("2 arrived requests still wait for a viewer")).toBeTruthy();
    expect(screen.getByText("Dune")).toBeTruthy();
    expect(screen.getByText("50%")).toBeTruthy();
    expect(screen.getByText("25%")).toBeTruthy();
    expect(screen.getByText("Sci-Fi")).toBeTruthy();
    expect(screen.getByText("20%")).toBeTruthy();
  });
});
