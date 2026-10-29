import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

// Issue 270: so many games of each a day — what is left told before a game, and none to start once all are
// played (the server refuses them as well).

const fake = vi.hoisted(() => ({
  handler: (_: Request): Response | Promise<Response> => new Response(null),
}));
vi.mock("../../../src/api/client", async (importOriginal) => {
  const { installFakeApi } = await import("../../support/fake-api");
  const installed = installFakeApi();
  Object.defineProperty(installed, "handler", { get: () => fake.handler });
  return importOriginal();
});

import SoloPage from "../../../src/features/games/SoloPage";
import { json } from "../../support/fake-api";

function show(today: number) {
  fake.handler = (request) => {
    const path = new URL(request.url).pathname;
    if (path === "/api/v1/games")
      return json(200, {
        enabled: true,
        party: true,
        cinemot: null,
        parties: [],
        games: [
          {
            key: "poster",
            kind: "rounds",
            solo: true,
            party: true,
            rounds: 6,
            seconds: 25,
            per_day: 3,
            today,
          },
        ],
      });
    return json(200, { game: "poster", period: "week", entries: [], me: null });
  };
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <RouterProvider
        router={createMemoryRouter([{ path: "/games/play/:game", element: <SoloPage /> }], {
          initialEntries: ["/games/play/poster"],
        })}
      />
    </QueryClientProvider>,
  );
}

afterEach(() => cleanup());

describe("issue 270 — games a day", () => {
  it("tells the games left today", async () => {
    show(1);
    expect(await screen.findByText("2 games left today (of 3)")).toBeTruthy();
    expect((screen.getByRole("button", { name: "Start" }) as HTMLButtonElement).disabled).toBe(false);
  });

  it("starts none once all of the day's are played", async () => {
    show(3);
    expect(await screen.findByText(/That's all for today: 3 games a day/)).toBeTruthy();
    expect((screen.getByRole("button", { name: "Start" }) as HTMLButtonElement).disabled).toBe(true);
  });
});
