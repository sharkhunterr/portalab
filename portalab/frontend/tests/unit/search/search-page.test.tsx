import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router";
import { describe, expect, it, vi } from "vitest";

// 008 T017/T020/T026 — grouped results with per-group states; filters update the URL in place (query
// kept); an unavailable source shows its own state; empty results offer a next action; the assistant is
// separate (its outage never hides results); snippets are rendered as text with <mark> highlights.

const fake = vi.hoisted(() => ({
  handler: (_: Request): Response | Promise<Response> => new Response(null),
}));
vi.mock("../../../src/api/client", async (importOriginal) => {
  const { installFakeApi } = await import("../../support/fake-api");
  const installed = installFakeApi();
  Object.defineProperty(installed, "handler", { get: () => fake.handler });
  return importOriginal();
});

import { AnnounceProvider } from "../../../src/design-system/a11y/Announce";
import { parseEvents } from "../../../src/features/search/assist/useSearchAssist";
import { paramsFrom, SearchPage, toSearch } from "../../../src/features/search/SearchPage";
import { json } from "../../support/fake-api";

const item = (kind: string, id: string, title: string, snippet = [{ text: title, hit: false }]) => ({
  kind,
  id,
  title,
  url_ref: `/${kind}/${id}`,
  snippet,
  language: null,
  matched_by: "exact",
  score: 1,
  facets: {},
});

function result(body: { kinds?: string[] | null; filters?: Record<string, string[]>; q?: string }) {
  const services = {
    kind: "services",
    label_key: "search.kind.services",
    state: "ok",
    items: (body.filters?.state ?? []).includes("error")
      ? [item("services", "s2", "Café Books")]
      : [
          item("services", "s1", "<b>Jellyfin</b>", [{ text: "<b>Jellyfin</b>", hit: true }]),
          item("services", "s2", "Café Books"),
        ],
    next_cursor: null,
    facets: [
      {
        key: "state",
        label_key: "search.facet.state",
        kind: "enum",
        values: [],
        counts: { enabled: 1, error: 1 },
      },
    ],
  };
  const users = {
    kind: "users",
    label_key: "search.kind.users",
    state: "unavailable",
    items: [],
    next_cursor: null,
    facets: [],
  };
  const groups = body.kinds?.length
    ? [services].filter((g) => body.kinds?.includes(g.kind))
    : [services, users];
  const total = groups.reduce((n, g) => n + g.items.length, 0);
  return {
    request_id: "r1",
    groups: body.q === "nothing" ? [] : groups,
    took_ms: 3,
    total: body.q === "nothing" ? 0 : total,
    semantic: "unavailable",
  };
}

function renderPage(path: string) {
  const bodies: Array<Record<string, unknown>> = [];
  fake.handler = async (request) => {
    const url = new URL(request.url);
    if (url.pathname === "/api/v1/search") {
      const body = (await request.json()) as Record<string, unknown>;
      bodies.push(body);
      return json(200, result(body as never));
    }
    if (url.pathname === "/api/v1/me/search-history")
      return json(200, [
        {
          id: "h1",
          query: "media",
          mode: "mixed",
          filters: {},
          count: 1,
          performed_at: "2026-10-01T00:00:00Z",
        },
      ]);
    return json(404, {});
  };
  const router = createMemoryRouter([{ path: "/search", element: <SearchPage /> }], {
    initialEntries: [path],
  });
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <AnnounceProvider>
        <RouterProvider router={router} />
      </AnnounceProvider>
    </QueryClientProvider>,
  );
  return { router, bodies };
}

describe("search page", () => {
  it("shows grouped results with their own states and plain-text highlights", async () => {
    renderPage("/search?q=jelly");
    const link = await screen.findByRole("link", { name: "<b>Jellyfin</b>" });
    expect(link.getAttribute("href")).toBe("/services/s1");
    expect(document.querySelector("mark")?.textContent).toBe("<b>Jellyfin</b>");
    expect(document.querySelector("b")).toBeNull(); // never parsed as HTML
    const users = screen.getByRole("heading", { name: /People/ }).closest("section") as HTMLElement;
    expect(within(users).getByText("This source is not available right now.")).toBeTruthy();
    expect(screen.getByText(/Meaning-based search is not available/)).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Assistant analysis" })).toBeTruthy();
  });

  it("applies filters through the URL without losing the query", async () => {
    const { router, bodies } = renderPage("/search?q=books");
    fireEvent.click(await screen.findByRole("button", { name: "error 1" }));
    await waitFor(() => expect(router.state.location.search).toBe("?q=books&f.state=error"));
    await waitFor(() => expect(bodies.at(-1)).toMatchObject({ q: "books", filters: { state: ["error"] } }));
    expect((screen.getByRole("searchbox") as HTMLInputElement).value).toBe("books");
    fireEvent.click(screen.getByRole("button", { name: "Services" }));
    await waitFor(() => expect(router.state.location.search).toBe("?q=books&type=services&f.state=error"));
  });

  it("offers a next action when nothing matches, and history before searching", async () => {
    renderPage("/search?q=nothing");
    expect(await screen.findByText("Nothing matches “nothing”.")).toBeTruthy();
    expect(screen.getByRole("link", { name: "Browse services" }).getAttribute("href")).toBe("/services");
  });

  it("lists recent searches when no query is typed", async () => {
    renderPage("/search");
    expect(await screen.findByRole("button", { name: "media" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Remove “media”" })).toBeTruthy();
  });
});

describe("url state and assist events", () => {
  it("round-trips search params", () => {
    const params = paramsFrom(new URLSearchParams("q=a&type=users&f.state=on&f.state=off&mode=exact"));
    expect(params).toEqual({ q: "a", mode: "exact", kinds: ["users"], filters: { state: ["on", "off"] } });
    expect(toSearch(params).toString()).toBe("q=a&mode=exact&type=users&f.state=on&f.state=off");
  });

  it("keeps source references and synthesis apart", () => {
    const events = parseEvents(
      'event: source_ref\ndata: {"kind":"users","id":"1"}\n\nevent: synthesis\ndata: {"text":"x"}\n\nevent: bad\ndata: {oops',
    );
    expect(events.map((e) => e.type)).toEqual(["source_ref", "synthesis"]);
  });
});
