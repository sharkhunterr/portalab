import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import type { ReactNode } from "react";
import { createMemoryRouter, RouterProvider } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

// Issue 363 — asking the team for a title no service asks for: the form filled from a title told absent, a
// title another member asked for turned into « I want it too », my requests and the others' to want too; a
// book told absent leads to it while the requests take books.

const fake = vi.hoisted(() => ({
  handler: (_: Request): Response | Promise<Response> => new Response(null),
}));
vi.mock("../../../src/api/client", async (importOriginal) => {
  const { installFakeApi } = await import("../../support/fake-api");
  const installed = installFakeApi();
  Object.defineProperty(installed, "handler", { get: () => fake.handler });
  return importOriginal();
});

import { KnownCard } from "../../../src/features/media/people/PersonPage";
import { AskLists, RequestsPage } from "../../../src/features/requests/RequestsPage";
import { json } from "../../support/fake-api";

const OPTIONS = { kinds: ["book", "game"], price: 0, left: { book: null, game: 2 }, quotas: {} };

function asked(id: string, title: string, extra: Record<string, unknown> = {}) {
  return {
    id,
    kind: "book",
    title,
    creators: ["Robin Hobb"],
    year: null,
    details: {},
    ids: {},
    note: null,
    status: "new",
    reason: null,
    supporters: 1,
    mine: false,
    asked: false,
    route: null,
    object_id: null,
    created_at: "2026-11-06T10:00:00Z",
    updated_at: "2026-11-06T10:00:00Z",
    ...extra,
  };
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

describe("title requests", () => {
  it("turns a title another member asked for into « I want it too »", async () => {
    const posted: Array<{ path: string; body: unknown }> = [];
    fake.handler = async (request) => {
      const path = new URL(request.url).pathname;
      if (path === "/api/v1/requests/options") return json(200, OPTIONS);
      if (path === "/api/v1/requests" && request.method === "GET")
        return json(200, {
          mine: [asked("r1", "Le Prophète blanc", { mine: true, asked: true })],
          open: [
            asked("r1", "Le Prophète blanc", { mine: true }),
            asked("r2", "Fool's Errand", { supporters: 3 }),
          ],
        });
      if (path === "/api/v1/requests" && request.method === "POST") {
        posted.push({ path, body: await request.json() });
        return json(409, { code: "requests.already_asked", title: "Asked", request_id: "r2" });
      }
      if (path === "/api/v1/requests/r2/support") {
        posted.push({ path, body: null });
        return json(200, asked("r2", "Fool's Errand", { supporters: 4, mine: true }));
      }
      return json(404, {});
    };
    renderAt("/requests?kind=book&title=Fool%27s%20Errand&creator=Robin%20Hobb", [
      { path: "/requests", element: <RequestsPage /> },
    ]);
    const title = (await screen.findByLabelText("Title")) as HTMLInputElement;
    expect(title.value).toBe("Fool's Errand");
    expect((screen.getByLabelText("Author, studio or creator") as HTMLInputElement).value).toBe("Robin Hobb");
    fireEvent.click(screen.getByRole("button", { name: "Send the request" }));
    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toContain("Another member asked for it already.");
    expect(posted[0]?.body).toMatchObject({ kind: "book", title: "Fool's Errand", creators: ["Robin Hobb"] });
    fireEvent.click(within(alert).getByRole("button", { name: /I want it too/ }));
    await waitFor(() => expect(posted.map((p) => p.path)).toContain("/api/v1/requests/r2/support"));
    expect((await screen.findByRole("status")).textContent).toContain("4 members want « Fool's Errand »");
  });

  it("lists my requests and the others' to want too, in « My requests » (issue 375)", async () => {
    fake.handler = async (request) => {
      const path = new URL(request.url).pathname;
      if (path === "/api/v1/requests/options") return json(200, OPTIONS);
      if (path === "/api/v1/requests")
        return json(200, {
          mine: [asked("r1", "Le Prophète blanc", { mine: true, asked: true })],
          open: [
            asked("r1", "Le Prophète blanc", { mine: true }),
            asked("r2", "Fool's Errand", { supporters: 3 }),
          ],
        });
      return json(404, {});
    };
    renderAt("/media/requests", [{ path: "/media/requests", element: <AskLists /> }]);
    // mine, then the others' open requests (mine left out)
    const mine = await screen.findByRole("list", { name: "My requests" });
    expect(within(mine).getByText("Le Prophète blanc")).toBeTruthy();
    const others = screen.getByRole("list", { name: "The other members' requests" });
    expect(within(others).getAllByRole("listitem")).toHaveLength(1);
    expect(within(others).getByText("3 members want it")).toBeTruthy();
  });

  it("leads from a book told absent to its request", async () => {
    fake.handler = (request) =>
      new URL(request.url).pathname === "/api/v1/requests/options" ? json(200, OPTIONS) : json(404, {});
    const credit = {
      tmdb_id: "917",
      kind: "book",
      title: "The Golden Fool",
      year: 2002,
      role: null,
      department: "writing",
      poster: null,
      image_id: null,
      rating: null,
      votes: 0,
      status: "absent",
      object_id: null,
      route: null,
      cover: null,
    };
    renderAt("/media/person", [
      {
        path: "/media/person",
        element: (
          <ul>
            <KnownCard credit={credit as never} askable={false} creator="Robin Hobb" />
          </ul>
        ),
      },
    ]);
    const button = await screen.findByRole("button", { name: /Ask for it/ });
    expect(screen.queryByText("Not here")).toBeNull(); // the button says it is not here
    // issue 377: the request in a dialog, filled from the title
    fireEvent.click(button);
    const dialog = await screen.findByRole("dialog");
    expect((within(dialog).getByLabelText("Title") as HTMLInputElement).value).toBe("The Golden Fool");
    expect((within(dialog).getByLabelText("Author, studio or creator") as HTMLInputElement).value).toBe(
      "Robin Hobb",
    );
    expect((within(dialog).getByLabelText("Year") as HTMLInputElement).value).toBe("2002");
  });

  it("leads from an audiobook the library has to asking for the book (issue 376)", async () => {
    fake.handler = (request) =>
      new URL(request.url).pathname === "/api/v1/requests/options" ? json(200, OPTIONS) : json(404, {});
    const credit = {
      tmdb_id: "427336",
      kind: "audiobook",
      title: "L'apprenti assassin",
      year: 1995,
      role: null,
      department: "writing",
      poster: null,
      image_id: null,
      rating: null,
      votes: 0,
      status: "available",
      object_id: "0190f0a0-0000-7000-8000-0000000000b2",
      route: "/media/0190f0a0-0000-7000-8000-0000000000b2",
      cover: null,
      sheet: "/media/book?service=s1&ref=427336",
    };
    renderAt("/media/person", [
      {
        path: "/media/person",
        element: (
          <ul>
            <KnownCard credit={credit as never} askable={false} />
          </ul>
        ),
      },
    ]);
    const link = await screen.findByRole("link", { name: /Ask for the book/ });
    expect(link.getAttribute("href")).toBe("/media/book?service=s1&ref=427336");
  });
});
