import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
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
      if (name === "history") return json(500, { code: "error" });
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
    const history = (await screen.findByRole("heading", { name: "History" })).closest(
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
    fireEvent.click(screen.getByRole("button", { name: "Request" }));
    expect(await screen.findByText("You have used your requests for this period.")).toBeTruthy();
    expect(posts).toEqual(["/api/v1/media/requests"]);
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
    renderAt("/media/requests", [{ path: "/media/requests", element: <RequestsPage /> }]);
    expect(await screen.findByText(/2 requests left this period/)).toBeTruthy();
    expect(screen.getByText(/1 extra request/)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Cancel: Arrival" }));
  });
});
