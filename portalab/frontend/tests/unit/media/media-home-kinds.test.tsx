import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { describe, expect, it, vi } from "vitest";

// Issue 435 — the media home has a row of what arrived last for each kind the library holds (books,
// audiobooks, games, music); a kind with nothing new has no row.

const fake = vi.hoisted(() => ({
  handler: (_: Request): Response | Promise<Response> => new Response(null),
}));
vi.mock("../../../src/api/client", async (importOriginal) => {
  const { installFakeApi } = await import("../../support/fake-api");
  const installed = installFakeApi();
  Object.defineProperty(installed, "handler", { get: () => fake.handler });
  return importOriginal();
});

import { MediaHome } from "../../../src/features/media/home/MediaHome";
import { json } from "../../support/fake-api";

const card = (id: string, title: string, kind: string) => ({
  id,
  kind,
  title,
  year: 2020,
  image_id: null,
  available: true,
  requested: false,
  age: null,
  kept: false,
  at: "2026-11-14T10:00:00Z",
});

describe("the media home's kinds", () => {
  it("shows a row for each kind with something new, opening that kind's catalog", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response(JSON.stringify({ ages: {} }), { status: 200 })),
    );
    fake.handler = (request) => {
      const url = new URL(request.url);
      if (url.pathname === "/api/v1/media/discovery/new") {
        const kind = url.searchParams.get("kind");
        const items =
          kind === "book"
            ? [card("00000000-0000-7000-8000-0000000000b1", "Dune", "book")]
            : kind === "game"
              ? []
              : kind
                ? []
                : [card("00000000-0000-7000-8000-0000000000f1", "Alien", "movie")];
        return json(200, { shelf: "new", items, next_action: null });
      }
      return json(404, {});
    };
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={client}>
        <MemoryRouter>
          <MediaHome />
        </MemoryRouter>
      </QueryClientProvider>,
    );
    await screen.findByText("Dune");
    const books = screen.getByRole("region", { name: "Recently added · Books" });
    expect(books.textContent).toContain("Dune");
    expect(books.querySelector("a.media-row__more")?.getAttribute("href")).toBe("/media/browse?kind=book");
    await waitFor(() => expect(screen.queryByRole("region", { name: "Recently added · Games" })).toBeNull());
    vi.unstubAllGlobals();
  });
});

describe("recently requested on the media home (issue 500)", () => {
  it("shows a game or a book the library lacks with its cover, its age and a way to its sheet", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response(JSON.stringify({ ages: {} }), { status: 200 })),
    );
    fake.handler = (request) => {
      const url = new URL(request.url);
      if (url.pathname === "/api/v1/media/requests/recent")
        return json(200, {
          items: [
            {
              id: null,
              kind: "game",
              title: "Paper Mario",
              state: "approved",
              image_id: null,
              cover: "/api/v1/media/game-images?service=s&ref=co25us&size=cover",
              sheet: "/media/game?service=s&ref=3349",
              age_rating: "PEGI 7",
              age: 7,
            },
            {
              id: null,
              kind: "book",
              title: "Assassin's Apprentice",
              state: "pending",
              image_id: null,
              cover: "/api/v1/media/book-covers?service=s&ref=c",
              sheet: "/media/book?service=s&ref=917",
              age: null,
            },
          ],
        });
      return json(404, {});
    };
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={client}>
        <MemoryRouter>
          <MediaHome />
        </MemoryRouter>
      </QueryClientProvider>,
    );
    const game = (await screen.findByText("Paper Mario")).closest("a") as HTMLAnchorElement;
    expect(game.getAttribute("href")).toBe("/media/game?service=s&ref=3349");
    expect(game.querySelector("img")?.getAttribute("src")).toContain("/api/v1/media/game-images");
    expect(game.querySelector(".age-badge")?.textContent).toContain("7+");
    const book = screen.getByText("Assassin's Apprentice").closest("a") as HTMLAnchorElement;
    expect(book.getAttribute("href")).toBe("/media/book?service=s&ref=917");
    expect(book.querySelector(".age-badge")?.textContent?.startsWith("?")).toBe(true); // unrated, as a library title
    vi.unstubAllGlobals();
  });
});
