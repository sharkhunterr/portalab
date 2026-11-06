import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import type { ReactNode } from "react";
import { createMemoryRouter, RouterProvider } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

// Issue 363, issue 378 — asking for a book, a game… as a film is asked for (the portal's own request): the
// form filled from a title told absent or an address; a book told absent leads to it while the team takes
// books; an audiobook the library has leads to asking for the book.

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
import { RequestsPage } from "../../../src/features/requests/RequestsPage";
import { json } from "../../support/fake-api";

const OPTIONS = { kinds: ["book", "game"], known: ["album", "audiobook", "book", "game"] };

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
  it("asks for a book as a film is asked for, and says when it is asked already", async () => {
    const posted: unknown[] = [];
    fake.handler = async (request) => {
      const path = new URL(request.url).pathname;
      if (path === "/api/v1/requests/options") return json(200, OPTIONS);
      if (path === "/api/v1/media/requests" && request.method === "POST") {
        posted.push(await request.json());
        return posted.length === 1
          ? json(201, { id: "r1", title: "Fool's Errand", kind: "book", state: "pending" })
          : json(409, { code: "media.request_duplicate", title: "Already requested" });
      }
      return json(404, {});
    };
    renderAt("/requests?kind=book&title=Fool%27s%20Errand&creator=Robin%20Hobb&id.isbn=9780553582444", [
      { path: "/requests", element: <RequestsPage /> },
    ]);
    const title = (await screen.findByLabelText("Title")) as HTMLInputElement;
    expect(title.value).toBe("Fool's Errand");
    fireEvent.click(screen.getByRole("button", { name: "Send the request" }));
    // issue 378: the portal's own request, with what was told of the book
    await waitFor(() => expect(posted).toHaveLength(1));
    expect(posted[0]).toMatchObject({
      kind: "book",
      title: "Fool's Errand",
      creators: ["Robin Hobb"],
      ids: { isbn: "9780553582444" },
    });
    expect((await screen.findByRole("status")).textContent).toContain("Fool's Errand");
    for (const link of screen.getAllByRole("link", { name: "See my requests" }))
      expect(link.getAttribute("href")).toBe("/media/requests");
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
