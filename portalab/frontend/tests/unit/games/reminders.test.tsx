import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router";
import { describe, expect, it, vi } from "vitest";

// Issue 313: the games' day tab reminds where the quests stand and which campaigns run, each a link.

const fake = vi.hoisted(() => ({
  handler: (_: Request): Response | Promise<Response> => new Response(null),
}));
vi.mock("../../../src/api/client", async (importOriginal) => {
  const { installFakeApi } = await import("../../support/fake-api");
  const installed = installFakeApi();
  Object.defineProperty(installed, "handler", { get: () => fake.handler });
  return importOriginal();
});

import GamesPage from "../../../src/features/games/GamesPage";
import { json } from "../../support/fake-api";

const soon = new Date(Date.now() + 3_600_000).toISOString();
const quest = (key: string, period: string | null, done: boolean) => ({
  key,
  kind: period ? "daily" : "quest",
  label: key,
  period,
  completed: done,
  resets_at: period ? soon : null,
  steps: [{ current: done ? 1 : 0, target: 1 }],
  rewards: [],
});

function show() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <RouterProvider router={createMemoryRouter([{ path: "/", element: <GamesPage /> }])} />
    </QueryClientProvider>,
  );
}

describe("issue 313 — the games' reminders", () => {
  it("shows the quests done out of all, today's left and the next one, and the running campaigns", async () => {
    fake.handler = (request) => {
      const path = new URL(request.url).pathname;
      if (path === "/api/v1/games")
        return json(200, { enabled: true, games: [], parties: [], party: false, cinemot: null });
      if (path === "/api/v1/community/quests")
        return json(200, {
          state: "available",
          items: [quest("visit", "day", true), quest("search", "day", false), quest("legend", null, false)],
        });
      if (path === "/api/v1/campaigns/active")
        return json(200, [
          { key: "halloween", name: "Halloween", ends_at: soon, boosts: [{ value: "xp", factor: 2 }] },
        ]);
      return json(404, {});
    };
    show();
    const quests = (await screen.findByText("1 / 3")).closest("a");
    expect(quests?.getAttribute("href")).toBe("/games/quests");
    expect(quests?.textContent).toContain("1 daily quest to do");
    expect(quests?.textContent).toContain("Next: search");
    const campaign = (await screen.findByText("Halloween")).closest("a");
    expect(campaign?.getAttribute("href")).toBe("/campaigns/halloween");
    expect(campaign?.textContent).toContain("×2");
  });
});
