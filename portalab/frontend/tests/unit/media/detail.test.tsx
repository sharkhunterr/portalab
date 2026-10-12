import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import type { ReactNode } from "react";
import { createMemoryRouter, RouterProvider } from "react-router";
import { describe, expect, it, vi } from "vitest";

// 024 T019 — the detail page renders independent section frames: one failing section shows its own state
// and retry while the others render; plugin blocks render declaratively and a failing block is isolated;
// availability / service health / sync are separate textual facts; the request flow reports the quota.

const fake = vi.hoisted(() => ({
  handler: (_: Request): Response | Promise<Response> => new Response(null),
}));
vi.mock("../../../src/api/client", async (importOriginal) => {
  const { installFakeApi } = await import("../../support/fake-api");
  const installed = installFakeApi();
  Object.defineProperty(installed, "handler", { get: () => fake.handler });
  return importOriginal();
});

import { CatalogPage } from "../../../src/features/media/catalog/CatalogPage";
import { DetailPage } from "../../../src/features/media/detail/DetailPage";
import { RequestsPage } from "../../../src/features/media/requests/RequestsPage";
import { json } from "../../support/fake-api";
import { INFO } from "./player-fixtures";

const ID = "0190f0a0-0000-7000-8000-0000000000aa";
const AS_OF = "2026-10-03T10:00:00Z";

function renderAt(path: string, routes: Array<{ path: string; element: ReactNode }>) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const router = createMemoryRouter(routes, { initialEntries: [path] });
  return render(
    <QueryClientProvider client={client}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
}

function section(name: string, state: string, data: Record<string, unknown> = {}) {
  return json(200, { name, state, as_of: AS_OF, data });
}

describe("media detail", () => {
  it("isolates sections and shows the three source facts", async () => {
    const posts: string[] = [];
    fake.handler = async (request) => {
      const path = new URL(request.url).pathname;
      if (request.method === "POST") {
        posts.push(path);
        return json(429, { code: "media.request_quota_exceeded", title: "Request quota reached" });
      }
      if (path === `/api/v1/media/${ID}`)
        return json(200, {
          id: ID,
          kind: "movie",
          title: "Arrival",
          year: 2016,
          available: false,
          image_id: null,
          status: "active",
          parent_id: null,
          position: null,
          overview: "Linguists.",
          genres: ["Sci-Fi"],
          ids: { tmdb: "329865" },
          sections: [],
        });
      const name = path.split("/").pop() ?? "";
      if (name === "viewing") return json(500, { code: "error" });
      if (name === "sources")
        return section("sources", "partial", {
          available: false,
          sources: [
            {
              service_id: "s1",
              service_name: "Plex",
              present: true,
              availability: "available",
              service_state: "unavailable",
              sync_status: "failed",
              sync_error: true,
            },
          ],
        });
      if (name === "statistics") return section("statistics", "insufficient_data", { min_cohort_size: 5 });
      if (name === "blocks")
        return section("blocks", "available", {
          blocks: [
            {
              key: "radio.facts",
              title_key: "radio:facts",
              template: "facts",
              state: "available",
              data: { rows: [["Rating", "8/10"]] },
            },
            { key: "radio.boom", title_key: "radio:boom", template: "facts", state: "unavailable", data: {} },
          ],
        });
      if (name === "info") return section("info", "available", { overview: "Linguists.", children: [] });
      return section(name, "no-data");
    };
    renderAt(`/media/${ID}`, [{ path: "/media/:objectId", element: <DetailPage /> }]);
    expect(await screen.findByRole("heading", { name: /Arrival/ })).toBeTruthy();
    const history = (await screen.findByRole("heading", { name: "My history" })).closest(
      "section",
    ) as HTMLElement;
    await waitFor(() => expect(within(history).getByRole("button", { name: "Retry" })).toBeTruthy());
    const sources = screen.getByRole("heading", { name: "Sources" }).closest("section") as HTMLElement;
    await waitFor(() => expect(within(sources).getByText("Plex")).toBeTruthy());
    expect(within(sources).getByText(/Service: unavailable/)).toBeTruthy();
    expect(within(sources).getByText(/The last sync failed/)).toBeTruthy();
    expect(await screen.findByText("Linguists.", { selector: "p" })).toBeTruthy();
    expect(await screen.findByText("8/10")).toBeTruthy();
    // 027: sections with nothing to tell are left out (no « not enough people », no « no data »)
    expect(screen.queryByRole("heading", { name: "Statistics" })).toBeNull();
    expect(screen.queryByRole("heading", { name: "Requests" })).toBeNull();
    // #4: a film with its TMDB id is asked for here, through the shared form (seasons, 4K, quota)
    expect(await screen.findByRole("button", { name: "Request" })).toBeTruthy();
    expect(posts).toEqual([]);
  });
});

describe("watching from the title's page", () => {
  it("resumes, starts over, or goes back to zero without playing", async () => {
    let resume = 1234;
    const resets: unknown[] = [];
    fake.handler = async (request) => {
      const path = new URL(request.url).pathname;
      if (path.endsWith("/player/reset")) {
        resets.push(await request.json());
        resume = 0;
        return new Response(null, { status: 204 });
      }
      if (path.endsWith("/player")) return json(200, { ...INFO, item: { ...INFO.item, resume_s: resume } });
      if (path === `/api/v1/media/${ID}`)
        return json(200, {
          id: ID,
          kind: "movie",
          title: "Alien",
          year: 1979,
          available: true,
          image_id: null,
          status: "active",
          parent_id: null,
          position: null,
          overview: null,
          genres: [],
          ids: {},
          sections: [],
        });
      return section(path.split("/").pop() ?? "", "no-data");
    };
    renderAt(`/media/${ID}`, [{ path: "/media/:objectId", element: <DetailPage /> }]);
    expect(await screen.findByRole("link", { name: "Resume" })).toBeTruthy();
    expect(screen.getByRole("link", { name: "Start over" }).getAttribute("href")).toBe(
      `/media/${ID}/watch?start=0`,
    );
    fireEvent.click(screen.getByRole("button", { name: "Back to zero" }));
    await waitFor(() => expect(resets).toEqual([{ item: "100" }]));
    expect(await screen.findByRole("link", { name: "Watch" })).toBeTruthy(); // nothing left to resume
    expect(screen.queryByRole("button", { name: "Back to zero" })).toBeNull();
  });
});

describe("the title's page at a glance", () => {
  it("shows availability and seen badges, folds the journey and lists my plays with the counts", async () => {
    fake.handler = async (request) => {
      const path = new URL(request.url).pathname;
      if (path.endsWith("/player"))
        return json(200, { ...INFO, item: { ...INFO.item, resume_s: 0, watched: true } });
      if (path.endsWith("/journey"))
        return json(200, {
          kind: "movie",
          available: true,
          request: { state: "available", requested_at: "2026-09-01T10:00:00Z" },
          manager: null,
          steps: [
            { key: "requested", status: "done", at: "2026-09-01T10:00:00Z", by: { me: true } },
            { key: "available", status: "done", at: "2026-09-03T10:00:00Z" },
          ],
          can_search: false,
          search: null,
        });
      if (path === `/api/v1/media/${ID}`)
        return json(200, {
          id: ID,
          kind: "movie",
          title: "Alien",
          year: 1979,
          available: true,
          image_id: null,
          status: "active",
          parent_id: null,
          position: null,
          overview: null,
          genres: [],
          ids: {},
          sections: [],
        });
      const name = path.split("/").pop() ?? "";
      if (name === "viewing")
        return section("viewing", "available", {
          mine: [
            {
              at: "2026-10-08T20:00:00Z",
              title: "Alien",
              series: null,
              kind: "movie",
              watched_s: 7000,
              duration_s: 7000,
              progress: 1,
              device: "Portalab",
              platform: null,
              stream: "copy",
              quality: "1080p",
            },
          ],
          mine_total: 1,
          status: "seen",
          percent: null,
          community: { plays: 12, viewers: 6 },
          min_cohort_size: 5,
        });
      return section(name, "no-data");
    };
    renderAt(`/media/${ID}`, [{ path: "/media/:objectId", element: <DetailPage /> }]);
    expect(await screen.findByText("Available", { selector: ".media-badge" })).toBeTruthy();
    expect(await screen.findByText("Watched", { selector: ".media-badge" })).toBeTruthy();
    // the journey folds into one line once the title is here
    const show = await screen.findByRole("button", { name: "See the journey" });
    expect(screen.getByText(/you requested it/)).toBeTruthy();
    fireEvent.click(show);
    expect(await screen.findByRole("button", { name: "Fold" })).toBeTruthy();
    // my history, and how many watched it (no names)
    expect(await screen.findByRole("heading", { name: "My history" })).toBeTruthy();
    expect(screen.getByText("12 plays")).toBeTruthy();
    expect(screen.getByText("6 members watched it")).toBeTruthy();
    expect(screen.getByText(/Portalab · 1080P/)).toBeTruthy();
  });
});

describe("catalog and requests", () => {
  it("filters the catalog and lists requests with quota", async () => {
    const queries: string[] = [];
    fake.handler = (request) => {
      const url = new URL(request.url);
      if (url.pathname === "/api/v1/media") {
        queries.push(url.search);
        return json(200, {
          items: [{ id: ID, kind: "movie", title: "Arrival", year: 2016, available: true, image_id: null }],
          next_cursor: null,
        });
      }
      if (request.method === "POST") return json(200, { id: "r1", state: "cancelled" });
      if (url.pathname === "/api/v1/me/media/requests/insights")
        return json(200, {
          period: { key: "365d", start: null },
          summary: { total: 1, pending: 1, approved: 0, available: 0, declined: 0 },
          previous_total: 0,
          by_kind: { movie: 1, series: 0 },
          timeline: { unit: "day", points: [{ date: "2026-10-01", count: 1, previous: 0 }] },
          watched: { requested: 1, watched: 0, rate: 0 },
          ranking: { position: 1, total: 3, count: 1, delta: null },
          top_watched: [],
          genres: { requested: [], watched: [] },
          quota: { base_remaining: 2, extra_units: 1 },
        });
      if (url.pathname === "/api/v1/me/media/requests/list")
        return json(200, {
          items: [
            {
              request_id: "r1",
              id: ID,
              title: "Arrival",
              kind: "movie",
              state: "pending",
              requested_at: AS_OF,
              updated_at: AS_OF,
              image_id: null,
              route: `/media/${ID}`,
            },
          ],
        });
      return json(200, {
        items: [
          {
            id: "r1",
            object_id: ID,
            title: "Arrival",
            kind: "movie",
            state: "pending",
            service_id: "s",
            requested_at: AS_OF,
            updated_at: AS_OF,
          },
        ],
        quota: { base_remaining: 2, extra_units: 1 },
      });
    };
    renderAt("/media/browse", [{ path: "/media/browse", element: <CatalogPage /> }]);
    expect(await screen.findByRole("link", { name: "Arrival" })).toBeTruthy();
    expect(screen.getByText(/Movie · 2016 · Available/)).toBeTruthy();
    fireEvent.change(screen.getByLabelText("Search titles"), { target: { value: "arr" } });
    fireEvent.change(screen.getByLabelText("Availability"), { target: { value: "available" } });
    fireEvent.click(screen.getByRole("button", { name: "Apply" }));
    await waitFor(() =>
      expect(queries.some((q) => q.includes("q=arr") && q.includes("availability=available"))).toBe(true),
    );
    // the overview's card: the count, where they stand, the quota and the bought requests (#3)
    renderAt("/media/requests", [{ path: "/media/requests", element: <RequestsPage /> }]);
    expect(await screen.findByText(/1 request bought in the shop/)).toBeTruthy();
    expect(screen.getByText(/2 left of/)).toBeTruthy();
    cleanup();
    renderAt("/media/requests?tab=list", [{ path: "/media/requests", element: <RequestsPage /> }]);
    fireEvent.click(await screen.findByRole("button", { name: "Cancel: Arrival" }));
  });
});
