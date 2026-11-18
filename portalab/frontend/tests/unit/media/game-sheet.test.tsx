import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

// Issue 368 — a game the library lacks, as the game database tells it, laid out as a library game: its
// summary and facts, its franchises, its platforms each to ask for (the platform and its IGDB id carried to
// the request); the library's page instead when it has it. Issue 498: the platform is asked for (chosen
// among the game's, set when asked on one), and once asked the sheet follows the request instead.

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

const posted: unknown[] = [];

function renderSheet(sheet: Record<string, unknown>, mine: Record<string, unknown>[] = []) {
  posted.length = 0;
  fake.handler = async (request) => {
    const path = new URL(request.url).pathname;
    if (path === "/api/v1/media/game") return json(200, sheet);
    if (path === "/api/v1/me/media/requests/list") return json(200, { items: mine });
    if (path === "/api/v1/media/game-extras")
      return json(200, {
        videos: [{ index: 0, site: "youtube", youtube: "abcdefghijk", name: "Trailer", kind: "trailer" }],
        images: [
          { index: 0, kind: "screenshot", preview: "/p0", full: "/f0" },
          { index: 1, kind: "artwork", preview: "/p1", full: "/f1" },
        ],
      });
    if (path === "/api/v1/me/media/follows") return json(200, { items: [] });
    if (path === "/api/v1/me/media/requests/r9/journey")
      return json(200, {
        kind: "game",
        available: false,
        request: { state: "approved", requested_at: "2026-11-17T23:00:00Z" },
        manager: null,
        steps: [
          { key: "requested", status: "done", at: "2026-11-17T23:00:00Z", by: { me: true } },
          { key: "approved", status: "done", at: "2026-11-17T23:04:00Z" },
          { key: "team", status: "current", at: "2026-11-17T23:04:00Z" },
          { key: "available", status: "upcoming" },
        ],
        can_search: false,
        search: null,
        asked: { details: { platform: "NES" }, reason: "Je cherche" },
        route: null,
      });
    if (path === "/api/v1/media/requests" && request.method === "POST") {
      posted.push(await request.json());
      return json(201, { id: "r1", title: "asked", supporters: 1 });
    }
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
    // issue 377: asked in a dialog, on that platform
    fireEvent.click(within(platforms).getByRole("button", { name: /Ask for it on NES/ }));
    const dialog = await screen.findByRole("dialog");
    expect((within(dialog).getByLabelText("Platform") as HTMLSelectElement).value).toBe("NES");
    fireEvent.click(within(dialog).getByRole("button", { name: "Send the request" }));
    await waitFor(() => expect(posted).toHaveLength(1));
    expect(posted[0]).toMatchObject({
      kind: "game",
      title: "Zelda II: The Adventure of Link",
      creators: ["Nintendo R&D4"],
      year: 1987,
      details: { platform: "NES" },
      ids: { igdb: "1025" }, // issue 378: one per scheme, as every request's
    });
  });

  it("asks for the platform when asked from the top of the sheet (issue 498)", async () => {
    renderSheet(SHEET);
    await screen.findByRole("heading", { name: "Zelda II: The Adventure of Link" });
    fireEvent.click(screen.getByRole("button", { name: "Ask for it" }));
    const dialog = await screen.findByRole("dialog");
    const platform = within(dialog).getByLabelText("Platform") as HTMLSelectElement;
    expect(platform.value).toBe(""); // two platforms: the member chooses
    expect([...platform.options].map((o) => o.value)).toEqual(["", "NES", "Game Boy Advance"]);
    const send = within(dialog).getByRole("button", { name: "Send the request" }) as HTMLButtonElement;
    expect(send.disabled).toBe(true);
    fireEvent.change(platform, { target: { value: "Game Boy Advance" } });
    expect(send.disabled).toBe(false);
    fireEvent.click(send);
    await waitFor(() => expect(posted).toHaveLength(1));
    expect(posted[0]).toMatchObject({ details: { platform: "Game Boy Advance" } });
  });

  it("presets the only platform a game has (issue 498)", async () => {
    renderSheet({ ...SHEET, platforms: ["Nintendo GameCube"] });
    await screen.findByRole("heading", { name: "Zelda II: The Adventure of Link" });
    fireEvent.click(screen.getByRole("button", { name: "Ask for it" }));
    const dialog = await screen.findByRole("dialog");
    expect((within(dialog).getByLabelText("Platform") as HTMLSelectElement).value).toBe("Nintendo GameCube");
  });

  it("follows the request once asked, with no second one (issue 498)", async () => {
    renderSheet(SHEET, [
      {
        request_id: "r9",
        id: null,
        title: SHEET.title,
        kind: "game",
        state: "approved",
        stage: "with_team",
        requested_at: "2026-11-17T23:00:00Z",
        image_id: null,
        route: null,
        sheet: "/media/game?service=s1&ref=1025",
        details: { platform: "NES" },
      },
    ]);
    await screen.findByRole("heading", { name: "Zelda II: The Adventure of Link" });
    expect(await screen.findByText("Being looked for", { selector: ".media-badge" })).toBeTruthy();
    expect(
      (await screen.findAllByText("The team is looking for it", { exact: false })).length,
    ).toBeGreaterThan(0);
    expect(screen.getByText("NES", { selector: "dd" })).toBeTruthy();
    expect(screen.getByText("« Je cherche »")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Ask for it" })).toBeNull();
    expect(screen.queryByRole("button", { name: /Ask for it on/ })).toBeNull();
  });

  it("says the age its game database gives it (issue 500)", async () => {
    renderSheet({ ...SHEET, age_rating: "PEGI 7", age: 7 });
    await screen.findByRole("heading", { name: "Zelda II: The Adventure of Link" });
    expect(document.querySelector(".age-badge")?.textContent).toContain("7+");
  });

  it("is laid out as a library game's page: production, videos, pictures, follow (issue 501)", async () => {
    renderSheet(SHEET);
    await screen.findByRole("heading", { name: "Zelda II: The Adventure of Link" });
    expect(screen.getByRole("heading", { name: "Production" })).toBeTruthy();
    expect(screen.getByText("Nintendo R&D4")).toBeTruthy(); // its studio in the production block
    expect(await screen.findByRole("list", { name: "Pictures" })).toBeTruthy();
    expect(screen.getByRole("list", { name: "Videos" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Follow" })).toBeTruthy();
  });

  it("opens the library's page when the library has it", async () => {
    renderSheet({ ...SHEET, library: "0190f0a0-0000-7000-8000-0000000000b2" });
    expect(await screen.findByText("The library's page")).toBeTruthy();
  });
});
