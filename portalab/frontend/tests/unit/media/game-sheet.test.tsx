import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, within } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

// Issue 368 — a game the library lacks, as the game database tells it, laid out as a library game: its
// summary and facts, its franchises, its platforms each to ask for (the platform and its IGDB id carried to
// the request); the library's page instead when it has it.

const fake = vi.hoisted(() => ({
  handler: (_: Request): Response | Promise<Response> => new Response(null),
}));
vi.mock("../../../src/api/client", async (importOriginal) => {
  const { installFakeApi } = await import("../../support/fake-api");
  const installed = installFakeApi();
  Object.defineProperty(installed, "handler", { get: () => fake.handler });
  return importOriginal();
});

import { GameSheetPage } from "../../../src/features/media/game/GameSheetPage";
import { json } from "../../support/fake-api";

const SHEET = {
  service: "s1",
  ref: "1025",
  title: "Zelda II: The Adventure of Link",
  summary: "Link's second quest.",
  storyline: null,
  year: 1987,
  release_date: "1987-01-14",
  cover: null,
  backdrop: null,
  images: [],
  genres: ["Adventure"],
  themes: [],
  modes: ["Single player"],
  platforms: ["NES", "Game Boy Advance"],
  developers: ["Nintendo R&D4"],
  publishers: ["Nintendo"],
  franchises: [
    { name: "The Legend of Zelda", route: "/media/collection?ref=series%3AThe%20Legend%20of%20Zelda" },
  ],
  names: {},
  rating: 7.1,
  votes: 300,
  trailer: null,
  library: null,
};

function renderSheet(sheet: Record<string, unknown>) {
  fake.handler = (request) => {
    const path = new URL(request.url).pathname;
    if (path === "/api/v1/media/game") return json(200, sheet);
    if (path === "/api/v1/requests/options")
      return json(200, { kinds: ["game"], price: 0, left: {}, quotas: {} });
    return json(404, {});
  };
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <RouterProvider
        router={createMemoryRouter(
          [
            { path: "/media/game", element: <GameSheetPage /> },
            { path: "/media/:id", element: <p>The library's page</p> },
          ],
          { initialEntries: ["/media/game?service=s1&ref=1025"] },
        )}
      />
    </QueryClientProvider>,
  );
}

afterEach(cleanup);

describe("a game's sheet", () => {
  it("tells the game and asks for it on a platform", async () => {
    renderSheet(SHEET);
    expect(await screen.findByRole("heading", { name: "Zelda II: The Adventure of Link" })).toBeTruthy();
    expect(screen.getByText("Link's second quest.")).toBeTruthy();
    expect(screen.getByRole("link", { name: "The Legend of Zelda" })).toBeTruthy();
    const platforms = screen.getByRole("list", { name: "Platforms" });
    const nes = within(platforms).getByRole("link", { name: /Ask for it on NES/ });
    const query = new URLSearchParams(nes.getAttribute("href")?.split("?")[1]);
    expect(Object.fromEntries(query)).toMatchObject({
      kind: "game",
      title: "Zelda II: The Adventure of Link",
      creator: "Nintendo R&D4",
      edition: "NES",
      "id.igdb": "1025",
    });
  });

  it("opens the library's page when the library has it", async () => {
    renderSheet({ ...SHEET, library: "0190f0a0-0000-7000-8000-0000000000b2" });
    expect(await screen.findByText("The library's page")).toBeTruthy();
  });
});
