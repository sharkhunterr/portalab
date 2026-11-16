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
import { AgeRating, GameDetails, PlayTimesFacts } from "../../../src/features/media/detail/GameView";
import { RatingsBlock } from "../../../src/features/media/detail/RatingsBlock";
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
  it("shows the seen badge, folds the journey and lists my plays with the counts", async () => {
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
    expect(await screen.findByText("Watched", { selector: ".media-badge" })).toBeTruthy();
    // issue 355: « Available » goes without saying beside « Watch » — the journey's card says since when
    expect(screen.queryByText("Available", { selector: ".media-badge" })).toBeNull();
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
          total: 1,
        });
      }
      if (url.pathname === "/api/v1/media/facets") {
        const book = url.searchParams.get("kind") === "book";
        return json(200, {
          years: { min: 1950, max: 2016 },
          genres: ["Science fiction"],
          authors: book ? ["Ted Chiang", "Frank Herbert"] : [],
          languages: book ? ["fr", "en"] : [],
          series: [],
          publishers: [],
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
    // #92: its standing is on the poster, inside the link (« Available Arrival »)
    expect(await screen.findByRole("link", { name: /Arrival/ })).toBeTruthy();
    expect(screen.getByText(/Movie · 2016/)).toBeTruthy();
    expect(document.querySelector('.discover-status[data-status="available"]')).toBeTruthy(); // its poster badge
    expect(screen.getByText("1 title")).toBeTruthy(); // issue 111: how many match
    // issue 111: applied as one types or chooses (no button), the active ones as chips to remove
    fireEvent.change(screen.getByLabelText("Search titles"), { target: { value: "arr" } });
    fireEvent.change(screen.getByLabelText("Availability"), { target: { value: "available" } });
    await waitFor(() =>
      expect(queries.some((q) => q.includes("q=arr") && q.includes("availability=available"))).toBe(true),
    );
    fireEvent.click(screen.getByRole("button", { name: "Books" }));
    await waitFor(() => expect(queries.some((q) => q.includes("kind=book"))).toBe(true));
    // the kind's own fields: a book's author (suggested), its language (a list, named in words)
    const author = await screen.findByLabelText("Author");
    expect(await screen.findByRole("option", { name: "French" })).toBeTruthy();
    fireEvent.change(author, { target: { value: "Ted Chiang" } });
    await waitFor(() => expect(queries.some((q) => /author=Ted(\+|%20)Chiang/.test(q))).toBe(true));
    fireEvent.change(screen.getByLabelText("Already seen"), { target: { value: "unseen" } });
    await waitFor(() => expect(queries.some((q) => q.includes("seen=unseen"))).toBe(true));
    fireEvent.click(screen.getByRole("button", { name: "Remove the filter Author : Ted Chiang" }));
    await waitFor(() => expect(queries.at(-1)).not.toContain("author="));
    expect(queries.at(-1)).toContain("seen=unseen");
    // issue 437: up to an age rating, unrated titles left out — each a chip
    expect(screen.queryByLabelText("Unrated titles")).toBeNull();
    fireEvent.change(screen.getByLabelText("Age rating"), { target: { value: "12" } });
    await waitFor(() => expect(queries.some((q) => q.includes("age=12"))).toBe(true));
    fireEvent.change(screen.getByLabelText("Unrated titles"), { target: { value: "exclude" } });
    await waitFor(() => expect(queries.at(-1)).toContain("unrated=exclude"));
    expect(screen.getByRole("button", { name: "Remove the filter Up to 12+" })).toBeTruthy();
    expect(screen.queryByRole("option", { name: "What I may watch" })).toBeNull(); // not a profile
    // the overview's card: the count, where they stand, the quota and the bought requests (#3) — #298: among
    // the statistics
    renderAt("/media/requests/stats", [{ path: "/media/requests/stats", element: <RequestsPage stats /> }]);
    expect(await screen.findByText(/1 request bought in the shop/)).toBeTruthy();
    expect(screen.getByText(/2 left of/)).toBeTruthy();
    cleanup();
    renderAt("/media/requests", [{ path: "/media/requests", element: <RequestsPage /> }]); // the list first
    fireEvent.click(await screen.findByRole("button", { name: "Cancel: Arrival" }));
  });
});

describe("a game's play times", () => {
  it("shows each style's length and players, skipping the unknown ones (#351)", () => {
    render(
      <PlayTimesFacts
        times={{
          main_story: { seconds: 19800, players: 145 },
          completionist: { seconds: 82800, players: null },
        }}
      />,
    );
    expect(screen.getByRole("heading", { name: "Time to beat" })).toBeTruthy();
    expect(screen.getByText("Main story")).toBeTruthy();
    expect(screen.getByText("145 players")).toBeTruthy();
    expect(screen.getByText("Completionist")).toBeTruthy();
    expect(screen.queryByText("Main + extras")).toBeNull();
    cleanup();
    const { container } = render(<PlayTimesFacts times={{}} />);
    expect(container.innerHTML).toBe("");
  });
});

describe("a game's page laid out like a film's (issue 467)", () => {
  it("tells its facts as chips, its summary, genres, production and play times", () => {
    render(
      <GameDetails
        genres={["Platform", "Game Boy", "Action"]}
        data={{
          title: "Alien vs Predator",
          overview: "In the year 2593…",
          platform: "Game Boy",
          publisher: "Activision",
          people: ["Activision", "ASK Kodansha"],
          released: "1993-07-01",
          tags: ["Action", "Sci-fi"],
          play_times: { main_story: { seconds: 7200, players: 3 } },
        }}
      />,
    );
    const section = screen.getByRole("region", { name: "About" });
    expect(within(section).getByText("In the year 2593…")).toBeTruthy();
    // the platform is a fact, not a genre; a tag already a genre is told once
    const genres = within(section).getByRole("list", { name: "Genres" });
    expect(
      within(genres)
        .getAllByRole("listitem")
        .map((li) => li.textContent),
    ).toEqual(["Platform", "Action"]);
    const tags = within(section).getByRole("list", { name: "Themes" });
    expect(
      within(tags)
        .getAllByRole("listitem")
        .map((li) => li.textContent),
    ).toEqual(["#Sci-fi"]);
    expect(within(section).getByText("ASK Kodansha")).toBeTruthy();
    expect(within(section).getByText("Activision")).toBeTruthy();
    expect(within(section).getByRole("heading", { name: "Time to beat" })).toBeTruthy();
  });

  it("shows nothing when nothing is known", () => {
    const { container } = render(<GameDetails genres={[]} data={{ title: "Unknown" }} />);
    expect(container.innerHTML).toBe("");
  });
});

describe("a game's age rating (issue 476)", () => {
  it("shows a PEGI rating as its official mark, read out as its age", () => {
    render(<AgeRating rating="PEGI 12" />);
    const mark = screen.getByRole("img", { name: /PEGI 12/ });
    expect(mark.getAttribute("src")).toContain("pegi-12");
  });

  it("shows any other rating system as its words", () => {
    render(<AgeRating rating="ESRB E10+" />);
    expect(screen.getByText("ESRB E10+")).toBeInTheDocument();
    expect(screen.queryByRole("img")).toBeNull();
  });

  it("puts the rating in the game's production block", () => {
    render(<GameDetails data={{ platform: "Game Boy Advance", content_rating: "PEGI 3" }} genres={[]} />);
    expect(screen.getByRole("img", { name: /PEGI 3/ })).toBeInTheDocument();
  });
});

describe("a title's classification in full (issue 478)", () => {
  const rating = {
    age: 12,
    country: "FR",
    basis: "tv",
    ratings: [],
    releases: [
      { country: "US", type: "cinema", certification: "R", age: 17, descriptors: [] },
      {
        country: "FR",
        type: "cinema",
        certification: "TP",
        age: 0,
        note: "Visa CNC 142250",
        descriptors: [],
      },
      { country: "FR", type: "tv", certification: "12", age: 12, note: "Novo19", descriptors: ["violence"] },
    ],
    cnc: { visa: 142250, decision: "Avertissement", warning: true, title: "Mad Max : Fury road", year: 2015 },
  };

  it("tells the age a profile is held to, the CNC's warning and each country's releases", () => {
    render(<RatingsBlock rating={rating} />);
    const block = screen.getByRole("region", { name: "Age rating" });
    expect(within(block).getByText(/following its TV rating/)).toBeInTheDocument();
    expect(within(block).getByText("All audiences, with a warning")).toBeInTheDocument();
    expect(within(block).getByText(/visa 142250/)).toBeInTheDocument();
    const headings = within(block)
      .getAllByRole("heading", { level: 4 })
      .map((h) => h.textContent);
    expect(headings).toEqual(["France", "United States"]); // the portal's country first
    const group = within(block).getByRole("heading", { name: "France" }).parentElement as HTMLElement;
    const france = within(group)
      .getAllByRole("definition")
      .map((d) => d.textContent ?? "");
    expect(france[0]).toContain("12"); // the TV first, as watched at home
    expect(france[0]).toContain("violence");
    expect(within(block).getAllByRole("definition")[0]?.textContent).toContain("following its TV rating");
  });

  it("is not shown without any release nor visa", () => {
    const { container } = render(<RatingsBlock rating={{ age: 12, ratings: [], releases: [], cnc: null }} />);
    expect(container).toBeEmptyDOMElement();
  });
});
