import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

// Issue 503 — a film the library lacks, laid out as a library title's page: its videos and pictures in
// carousels (asked by its TMDB id), beside its synopsis and cast.

const fake = vi.hoisted(() => ({
  handler: (_: Request): Response | Promise<Response> => new Response(null),
  asked: [] as string[],
}));
vi.mock("../../../src/api/client", async (importOriginal) => {
  const { installFakeApi } = await import("../../support/fake-api");
  const installed = installFakeApi();
  Object.defineProperty(installed, "handler", { get: () => fake.handler });
  return importOriginal();
});

import { DiscoverTitlePage } from "../../../src/features/media/discover/DiscoverTitlePage";
import { json } from "../../support/fake-api";

const FILM = {
  tmdb_id: "1125510",
  kind: "movie",
  title: "The Beast",
  year: 2026,
  overview: "Une limousine high-tech.",
  poster: null,
  backdrop: null,
  rating: 5.3,
  release_date: "2026-10-08",
  status: "unknown",
  object_id: null,
  request: null,
  route: "/media/discover/movie/1125510",
  genres: ["Action"],
  runtime: 99,
  tagline: null,
  cast: [],
  trailer: null,
  ids: { tmdb: "1125510" },
  seasons: [],
  four_k: false,
  metadata: {},
};

afterEach(cleanup);

describe("a film's page before asking for it", () => {
  it("shows its videos and pictures as a library title's page (issue 503)", async () => {
    fake.asked = [];
    fake.handler = async (request) => {
      const url = new URL(request.url);
      if (url.pathname === "/api/v1/media/discover/movie/1125510") return json(200, FILM);
      if (url.pathname === "/api/v1/media/discover-extras") {
        fake.asked.push(url.search);
        return json(200, {
          videos: [
            { index: 0, site: "youtube", youtube: "abcdefghijk", name: "Bande-annonce", kind: "trailer" },
          ],
          images: [
            { index: 0, kind: "backdrop", preview: "/p0", full: "/f0" },
            { index: 1, kind: "still", preview: "/p1", full: "/f1" },
          ],
        });
      }
      return json(200, {});
    };
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={client}>
        <RouterProvider
          router={createMemoryRouter(
            [{ path: "/media/discover/:kind/:tmdb", element: <DiscoverTitlePage /> }],
            {
              initialEntries: ["/media/discover/movie/1125510"],
            },
          )}
        />
      </QueryClientProvider>,
    );
    expect(await screen.findByRole("heading", { name: "The Beast" })).toBeTruthy();
    expect(await screen.findByRole("list", { name: "Pictures" })).toBeTruthy();
    expect(screen.getByRole("list", { name: "Videos" })).toBeTruthy();
    expect(fake.asked).toEqual(["?kind=movie&tmdb=1125510"]);
  });
});
