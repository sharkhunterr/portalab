import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { describe, expect, it, vi } from "vitest";

// Issue 356: the month's media bingo — squares ticked by the titles that fit them, lines lit when complete.

const fake = vi.hoisted(() => ({
  handler: (_: Request): Response | Promise<Response> => new Response(null),
}));
vi.mock("../../src/api/client", async (importOriginal) => {
  const { installFakeApi } = await import("../support/fake-api");
  const installed = installFakeApi();
  Object.defineProperty(installed, "handler", { get: () => fake.handler });
  return importOriginal();
});

import { BingoSection } from "../../src/features/games/Bingo";
import { json } from "../support/fake-api";

const KEYS = [
  "genre:horror",
  "era:1980",
  "country:JP",
  "kind:live",
  "genre:comedy",
  "review",
  "later",
  "series:pilot",
  "length:long",
];
const BY = { id: "m-1", title: "Alien", image_id: null, at: "2026-11-03T20:00:00Z" };

function view(ticked: number[]) {
  const cells = KEYS.map((key, i) => ({
    key,
    group: key.split(":")[0],
    by: ticked.includes(i) ? (key === "kind:live" ? { ...BY, id: null, title: "Kaamelott" } : BY) : null,
  }));
  const lines = [
    { key: "row:0", cells: [0, 1, 2] },
    { key: "row:1", cells: [3, 4, 5] },
    { key: "row:2", cells: [6, 7, 8] },
  ].map((line) => ({ ...line, done: line.cells.every((c) => ticked.includes(c)) }));
  return {
    month: "2026-11-01",
    ends_at: "2026-12-01T00:00:00Z",
    size: 3,
    cells,
    lines,
    squares: ticked.length,
    done_lines: lines.filter((l) => l.done).length,
    card: ticked.length === KEYS.length,
    players: 2,
    cards: 0,
  };
}

function show(data: unknown) {
  fake.handler = (request) =>
    new URL(request.url).pathname === "/api/v1/games/bingo" ? json(200, data) : json(200, []);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <BingoSection />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("the month's media bingo", () => {
  it("stamps the squares ticked and lights the lines complete", async () => {
    show(view([0, 1, 2, 3]));
    const grid = await screen.findByRole("list", { name: /4 squares ticked out of 9/ });
    const squares = within(grid).getAllByRole("listitem");
    expect(squares).toHaveLength(9);
    expect(squares[0]?.textContent).toContain("Some horror");
    expect(squares[2]?.textContent).toContain("Made in Japan");
    expect(squares[0]?.dataset.ticked).toBe("true");
    expect(squares[0]?.dataset.lit).toBe("true"); // the first row is complete
    expect(squares[3]?.dataset.lit).toBeUndefined();
    expect(within(squares[0] as HTMLElement).getByRole("link", { name: /Alien/ })).toBeTruthy();
    expect(squares[3]?.textContent).toContain("Kaamelott"); // live TV: no title page
    expect(squares[4]?.dataset.ticked).toBeUndefined();
    expect(screen.getByText(/2 members already have a line/)).toBeTruthy();
    expect(screen.queryByText(/Full card!/)).toBeNull();
  });

  it("celebrates the full card", async () => {
    show(view([0, 1, 2, 3, 4, 5, 6, 7, 8]));
    expect(await screen.findByText(/Full card!/)).toBeTruthy();
  });

  it("shows nothing when the bingo is not available", async () => {
    show({ detail: "off" });
    await vi.waitFor(() => expect(screen.queryByRole("region")).toBeNull());
  });
});
