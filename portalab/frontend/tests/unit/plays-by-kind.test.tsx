import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

// Issue 160 — plays by kind: one line per kind (episodes, films, audiobooks…) with its sittings, the works
// finished, the time, the XP and Coins — and, for the administrators, how many members played it.

const fake = vi.hoisted(() => ({
  handler: (_: Request): Response | Promise<Response> => new Response(null),
  requests: [] as Request[],
}));
vi.mock("../../src/api/client", async (importOriginal) => {
  const { installFakeApi } = await import("../support/fake-api");
  const installed = installFakeApi();
  Object.defineProperty(installed, "handler", { get: () => fake.handler });
  installed.requests = fake.requests;
  return importOriginal();
});

import { PlaysByKind } from "../../src/features/gamification/progression/PlaysByKind";
import { json } from "../support/fake-api";

const PLAYS = {
  kinds: [
    { play: "movie", sittings: 1, finished: 1, watched_s: 6000, xp: 130, coins: 5, members: 1 },
    { play: "episode", sittings: 3, finished: 2, watched_s: 2700, xp: 45, coins: 0, members: 2 },
  ],
  days: [{ day: "2026-10-19", sittings: { movie: 1, episode: 3 } }],
};

function show(admin: boolean) {
  fake.handler = () => json(200, PLAYS);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <PlaysByKind admin={admin} />
    </QueryClientProvider>,
  );
}

describe("plays by kind", () => {
  it("shows my plays kind by kind, with their time and gains", async () => {
    show(false);
    const table = await screen.findByRole("table", { name: "My plays by kind" });
    const film = within(table).getByRole("row", { name: /Films/ });
    expect(film).toHaveTextContent("1 h 40");
    expect(film).toHaveTextContent("130");
    expect(within(table).getByRole("row", { name: /Episodes/ })).toHaveTextContent("45 min");
    expect(within(table).getByRole("row", { name: /Total/ })).toHaveTextContent("175");
    expect(within(table).queryByRole("columnheader", { name: "Members" })).toBeNull();
    expect(fake.requests.at(-1)?.url).toContain("/api/v1/me/progression/plays");
  });

  it("counts the members for the administrators", async () => {
    show(true);
    const table = await screen.findByRole("table");
    expect(within(table).getByRole("columnheader", { name: "Members" })).toBeTruthy();
    expect(fake.requests.at(-1)?.url).toContain("/api/v1/admin/gamification/plays");
  });
});
