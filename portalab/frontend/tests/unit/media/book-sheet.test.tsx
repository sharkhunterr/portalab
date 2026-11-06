import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

// Issue 367 — a book the library lacks, as the book database tells it, laid out as a library title (issue
// 370): its authors leading to their page, its series, its editions; asking the team for the book or for
// one edition (its title, language, format and ISBN carried to the request); the library's page instead
// when it has it.

const fake = vi.hoisted(() => ({
  handler: (_: Request): Response | Promise<Response> => new Response(null),
}));
vi.mock("../../../src/api/client", async (importOriginal) => {
  const { installFakeApi } = await import("../../support/fake-api");
  const installed = installFakeApi();
  Object.defineProperty(installed, "handler", { get: () => fake.handler });
  return importOriginal();
});

import { BookSheetPage } from "../../../src/features/media/book/BookSheetPage";
import { json } from "../../support/fake-api";

const SHEET = {
  service: "s1",
  ref: "458644",
  title: "Fool's Quest",
  subtitle: null,
  description: "Years ago, they freed a dragon.\nNow, betrayed by his own people…",
  year: 2015,
  release_date: "2015-08-11",
  pages: 753,
  cover: null,
  authors: ["Robin Hobb"],
  series: [{ name: "Fitz and the Fool", position: 2, route: "/media/collection?ref=series%3AFitz" }],
  genres: ["Fantasy"],
  moods: ["dark"],
  rating: 8.9,
  votes: 348,
  readers: 887,
  editions: [
    {
      title: "Fool's Quest",
      language: "en",
      format: "Listened",
      audio: true,
      ids: { asin: ["B00XO0OGTO"] },
      publisher: "Random House Audio",
      year: 2015,
      cover: null,
    },
    {
      title: "Le Fou et l'Assassin, Intégrale 2",
      language: "fr",
      format: "Read",
      audio: false,
      ids: { isbn: ["9782290359303"] },
      publisher: "J'ai Lu",
      year: 2021,
      cover: null,
    },
  ],
  library: {},
};

const posted: unknown[] = [];

function renderSheet(sheet: Record<string, unknown>) {
  posted.length = 0;
  fake.handler = async (request) => {
    const path = new URL(request.url).pathname;
    if (path === "/api/v1/media/book") return json(200, sheet);
    if (path === "/api/v1/media/requests" && request.method === "POST") {
      posted.push(await request.json());
      return json(201, { id: "r1", title: "asked", supporters: 1 });
    }
    if (path === "/api/v1/requests/options")
      return json(200, { kinds: ["book", "audiobook"], price: 0, left: {}, quotas: {} });
    return json(404, {});
  };
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <RouterProvider
        router={createMemoryRouter(
          [
            { path: "/media/book", element: <BookSheetPage /> },
            { path: "/media/:id", element: <p>The library's page</p> },
          ],
          {
            initialEntries: ["/media/book?service=s1&ref=458644"],
          },
        )}
      />
    </QueryClientProvider>,
  );
}

afterEach(cleanup);

describe("a book's sheet", () => {
  it("tells the book and asks for it, or for one of its editions", async () => {
    renderSheet(SHEET);
    expect(await screen.findByRole("heading", { name: "Fool's Quest" })).toBeTruthy();
    expect(screen.getByRole("link", { name: "Robin Hobb" }).getAttribute("href")).toBe(
      "/media/people/Robin%20Hobb",
    );
    expect(screen.getByRole("link", { name: "Fitz and the Fool, volume 2" })).toBeTruthy();
    expect(screen.getByText(/Now, betrayed by his own people…/)).toBeTruthy();
    expect(screen.getByText("Not in the library")).toBeTruthy();
    const editions = screen.getByRole("list", { name: "Editions" });
    const [audio, paper] = within(editions).getAllByRole("listitem");
    // issue 377: asked in a dialog, filled from the edition
    fireEvent.click(within(paper as HTMLElement).getByRole("button", { name: /Ask for it/ }));
    const dialog = await screen.findByRole("dialog");
    expect((within(dialog).getByLabelText("Title") as HTMLInputElement).value).toBe(
      "Le Fou et l'Assassin, Intégrale 2",
    );
    expect((within(dialog).getByLabelText("Kind") as HTMLSelectElement).value).toBe("book");
    expect((within(dialog).getByLabelText("Edition") as HTMLInputElement).value).toBe("Read, J'ai Lu");
    fireEvent.click(within(dialog).getByRole("button", { name: "Send the request" }));
    await waitFor(() => expect(posted).toHaveLength(1));
    expect(posted[0]).toMatchObject({
      kind: "book",
      title: "Le Fou et l'Assassin, Intégrale 2",
      creators: ["Robin Hobb"],
      details: { language: "fr", edition: "Read, J'ai Lu" },
      ids: { isbn: "9782290359303" }, // issue 378: one per scheme, as every request's
    });
    fireEvent.keyDown(dialog, { key: "Escape" });
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    fireEvent.click(within(audio as HTMLElement).getByRole("button", { name: /Ask for it/ }));
    const listened = await screen.findByRole("dialog");
    expect((within(listened).getByLabelText("Kind") as HTMLSelectElement).value).toBe("audiobook");
  });

  it("opens the library's page when the library has the book", async () => {
    renderSheet({ ...SHEET, library: { book: "0190f0a0-0000-7000-8000-0000000000b2" } });
    expect(await screen.findByText("The library's page")).toBeTruthy();
  });

  it("leaves the book to ask for when the library has it as an audiobook only", async () => {
    renderSheet({ ...SHEET, library: { audiobook: "0190f0a0-0000-7000-8000-0000000000b2" } });
    const listened = await screen.findByRole("link", { name: /As an audiobook in the library/ });
    expect(listened.getAttribute("href")).toBe("/media/0190f0a0-0000-7000-8000-0000000000b2");
    const editions = screen.getByRole("list", { name: "Editions" });
    // the paper edition to ask for, not the audiobook it has
    const asked = within(editions).getAllByRole("button", { name: /Ask for it/ });
    expect(asked).toHaveLength(1);
    fireEvent.click(asked[0] as HTMLElement);
    const dialog = await screen.findByRole("dialog");
    expect((within(dialog).getByLabelText("Kind") as HTMLSelectElement).value).toBe("book");
  });
});
