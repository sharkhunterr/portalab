import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { createMemoryRouter, RouterProvider } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

// Issue 190: why a title is recommended, and judging titles one by one (swiped or with buttons).

const fake = vi.hoisted(() => ({
  calls: [] as { method: string; url: string; body: unknown }[],
  handler: (_: Request): Response | Promise<Response> => new Response(null),
}));
vi.mock("../../../src/api/client", async (importOriginal) => {
  const { installFakeApi } = await import("../../support/fake-api");
  const installed = installFakeApi();
  Object.defineProperty(installed, "handler", { get: () => fake.handler });
  return importOriginal();
});

import type { TasteCard } from "../../../src/features/media/taste/api";
import { TasteDeck } from "../../../src/features/media/taste/TasteDeck";
import { TasteRail } from "../../../src/features/media/taste/TasteRail";
import { json } from "../../support/fake-api";

function show(element: ReactNode) {
  fake.calls = [];
  fake.handler = async (request) => {
    const body = request.method === "GET" ? null : await request.clone().text();
    fake.calls.push({
      method: request.method,
      url: new URL(request.url).pathname,
      body: body && JSON.parse(body),
    });
    return request.method === "GET"
      ? json(200, { items: [] })
      : json(200, { object_id: "x", verdict: "like" });
  };
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const router = createMemoryRouter([{ path: "/", element }], { initialEntries: ["/"] });
  return render(
    <QueryClientProvider client={client}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
}

const card = (id: string, title: string, extra: Partial<TasteCard> = {}): TasteCard =>
  ({
    id,
    kind: "movie",
    title,
    year: 2014,
    available: true,
    image_id: null,
    genres: ["Science Fiction"],
    overview: null,
    rating: 8.4,
    author: null,
    reason: null,
    seen: false,
    verdict: null,
    ...extra,
  }) as TasteCard;

afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

describe("issue 190 — my taste", () => {
  it("says beside each recommendation why it is there", async () => {
    show(
      <TasteRail
        label="For you"
        items={[
          card("a", "Tenet", {
            reason: { kind: "director", name: "Christopher Nolan", titles: ["Inception", "Interstellar"] },
          }),
          card("b", "The Hobbit", { reason: { kind: "saga", name: "The Lord of the Rings", titles: [] } }),
        ]}
      />,
    );
    expect(await screen.findByText("Directed by Christopher Nolan")).toBeTruthy();
    expect(screen.getByText("The Lord of the Rings saga")).toBeTruthy();
    expect(screen.getByRole("link", { name: /Tenet/ }).getAttribute("title")).toBe(
      "Like Inception and Interstellar",
    );
  });

  it("judges a title with a button, then shows the next, and takes the answer back", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    show(<TasteDeck initial={[card("a", "Tenet"), card("b", "Dune"), card("c", "Arrival")]} />);
    expect(await screen.findByRole("heading", { name: "Tenet" })).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: /I like it/ }));
    await act(async () => {
      vi.advanceTimersByTime(400);
    });
    expect(await screen.findByRole("heading", { name: "Dune" })).toBeTruthy();
    expect(fake.calls).toContainEqual({
      method: "PUT",
      url: "/api/v1/me/media/taste/titles/a",
      body: { verdict: "like" },
    });
    // the arrow keys answer too: ← « not for me »
    fireEvent.keyDown(screen.getByRole("heading", { name: "Dune" }), { key: "ArrowLeft" });
    await act(async () => {
      vi.advanceTimersByTime(400);
    });
    expect(fake.calls).toContainEqual({
      method: "PUT",
      url: "/api/v1/me/media/taste/titles/b",
      body: { verdict: "dislike" },
    });
    fireEvent.click(await screen.findByRole("button", { name: /Undo « Dune »/ }));
    expect(await screen.findByRole("heading", { name: "Dune" })).toBeTruthy();
    expect(fake.calls.some((c) => c.method === "DELETE" && c.url === "/api/v1/me/media/taste/titles/b")).toBe(
      true,
    );
  });

  it("asks a title of mine whether I liked it", async () => {
    show(<TasteDeck initial={[card("a", "Inception", { seen: true })]} />);
    expect(await screen.findByText("Already in your history: liked it?")).toBeTruthy();
    expect(screen.getByRole("button", { name: /Skip/ })).toBeTruthy();
  });
});
