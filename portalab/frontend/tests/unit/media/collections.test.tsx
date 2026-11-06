import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, within } from "@testing-library/react";
import type { ReactNode } from "react";
import { createMemoryRouter, RouterProvider } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

// Issue 361 — a title's collection told the same way for a book, a game, a film: its kind of collection,
// its name leading to its page, the title's place in it and its other titles; the saga's page lists every
// film, the missing ones too.

const fake = vi.hoisted(() => ({
  handler: (_: Request): Response | Promise<Response> => new Response(null),
}));
vi.mock("../../../src/api/client", async (importOriginal) => {
  const { installFakeApi } = await import("../../support/fake-api");
  const installed = installFakeApi();
  Object.defineProperty(installed, "handler", { get: () => fake.handler });
  return importOriginal();
});

import { CollectionPage } from "../../../src/features/media/collections/CollectionPage";
import { CollectionRow } from "../../../src/features/media/collections/CollectionRow";
import { json } from "../../support/fake-api";

const BOOK = "0190f0a0-0000-7000-8000-0000000000b2";

function card(id: string, title: string, extra: Record<string, unknown> = {}) {
  return { id, kind: "book", title, year: 2015, available: true, image_id: null, requested: false, ...extra };
}

function renderAt(path: string, routes: Array<{ path: string; element: ReactNode }>) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <RouterProvider router={createMemoryRouter(routes, { initialEntries: [path] })} />
    </QueryClientProvider>,
  );
}

afterEach(cleanup);

describe("collections", () => {
  it("tells a book's series with its volume and its other volumes", async () => {
    fake.handler = (request) => {
      const path = new URL(request.url).pathname;
      if (path === `/api/v1/media/${BOOK}/collection`)
        return json(200, {
          ref: "series:Fire and Stone",
          source: "series",
          name: "Fire and Stone",
          poster: null,
          items: [
            card("0190f0a0-0000-7000-8000-0000000000b1", "Prometheus", { position: 1 }),
            card(BOOK, "Aliens", { position: 2 }),
          ],
          parts: [],
          askable: false,
        });
      return json(404, {});
    };
    renderAt(`/media/${BOOK}`, [{ path: "/media/:id", element: <CollectionRow objectId={BOOK} /> }]);
    const link = await screen.findByRole("link", { name: "Fire and Stone" });
    expect(link.getAttribute("href")).toBe("/media/collection?ref=series%3AFire%20and%20Stone");
    const block = link.closest("section") as HTMLElement;
    expect(within(block).getByText(/Volume 2 · 2 titles in the library/)).toBeTruthy();
    expect(within(block).getByText("This title")).toBeTruthy();
    expect(within(block).getByText("Volume 1")).toBeTruthy();
  });

  it("lists a saga's films, the missing ones to ask for", async () => {
    fake.handler = (request) => {
      const url = new URL(request.url);
      if (url.pathname === "/api/v1/media/collection" && url.searchParams.get("ref") === "tmdb:531241")
        return json(200, {
          ref: "tmdb:531241",
          source: "saga",
          name: "Spider-Man (MCU) - Saga",
          poster: null,
          items: [card(BOOK, "Spider-Man: Homecoming", { kind: "movie" })],
          parts: [
            {
              tmdb_id: "315635",
              kind: "movie",
              title: "Spider-Man: Homecoming",
              year: 2017,
              role: null,
              department: "saga",
              poster: null,
              image_id: null,
              rating: null,
              votes: 0,
              status: "available",
              object_id: BOOK,
              route: `/media/${BOOK}`,
            },
            {
              tmdb_id: "634649",
              kind: "movie",
              title: "No Way Home",
              year: 2021,
              role: null,
              department: "saga",
              poster: null,
              image_id: null,
              rating: null,
              votes: 0,
              status: "missing",
              object_id: null,
              route: "/media/discover/movie/634649",
            },
          ],
          askable: false,
        });
      return json(404, {});
    };
    renderAt("/media/collection?ref=tmdb%3A531241", [
      { path: "/media/collection", element: <CollectionPage /> },
    ]);
    expect(await screen.findByRole("heading", { name: "Spider-Man (MCU) - Saga" })).toBeTruthy();
    const films = screen.getByRole("list", { name: "The saga's films" });
    expect(within(films).getAllByRole("listitem")).toHaveLength(2);
    expect(
      within(films)
        .getByRole("link", { name: /No Way Home/ })
        .getAttribute("href"),
    ).toBe("/media/discover/movie/634649");
  });
});
