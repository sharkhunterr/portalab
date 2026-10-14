import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router";
import { describe, expect, it, vi } from "vitest";

// 027 — the gamification administration: the simple mode sets one pace (factor) for every gain from the
// progression chart; the detailed mode edits what each action gives as a form (fixed + per minute);
// streak tiers are saved sorted.

const fake = vi.hoisted(() => ({
  handler: (_: Request): Response | Promise<Response> => new Response(null),
}));
vi.mock("../../../src/api/client", async (importOriginal) => {
  const { installFakeApi } = await import("../../support/fake-api");
  const installed = installFakeApi();
  Object.defineProperty(installed, "handler", { get: () => fake.handler });
  return importOriginal();
});

import GamificationAdmin from "../../../src/features/gamification/admin/GamificationAdmin";
import { json } from "../../support/fake-api";

const TYPES = [
  {
    name: "media.playback_finished",
    owner: "module:media",
    fields: [
      { name: "duration_s", numeric: true },
      { name: "kind", numeric: false },
    ],
  },
  { name: "ticket.created", owner: "module:support", fields: [] },
];

// issue 104: two members, their gains by kind, day by day
const MEMBERS = [
  {
    user_id: "u1",
    name: "Noémie",
    balance: 60,
    gained: 45,
    sources: [
      { source: "media", amount: 30 },
      { source: "achievements", amount: 15 },
    ],
    days: [{ day: "2026-10-13", amounts: { media: 30, achievements: 15 } }],
    points: [
      { day: "2026-09-13", total: 15 },
      { day: "2026-10-13", total: 60 },
    ],
  },
  {
    user_id: "u2",
    name: "Admin",
    balance: 40,
    gained: 20,
    sources: [{ source: "quests", amount: 20 }],
    days: [{ day: "2026-10-12", amounts: { quests: 20 } }],
    points: [
      { day: "2026-09-13", total: 20 },
      { day: "2026-10-12", total: 40 },
    ],
  },
];

// issue 106: their detail — held, gained, spent, the levels reached
const DETAILS = [
  {
    user_id: "u1",
    name: "Noémie",
    level: 2,
    start_level: 1,
    xp: { balance: 120, gained: 100, spent: 0 },
    coins: { balance: 22, gained: 25, spent: 3 },
    contribution: { balance: 1, gained: 1, spent: 0 },
    level_ups: [{ level: 2, at: "2026-10-13T18:00:00Z", day: "2026-10-13" }],
    days: [
      { day: "2026-10-12", xp: 20, coins: 5, contribution: 0, spent_coins: 0, levels: [] },
      { day: "2026-10-13", xp: 80, coins: 20, contribution: 1, spent_coins: 3, levels: [2] },
    ],
  },
];

// issue 107: the journal, page by page (27 operations: a page of 25, then 2; the last one a correction)
function operation(n: number) {
  const fix = n === 27;
  return {
    id: `op${n}`,
    occurred_at: new Date(Date.UTC(2026, 9, 13, 12, 60 - n)).toISOString(),
    user_id: "u1",
    name: "Noémie",
    value: "xp",
    delta: fix ? -2 : 10,
    kind: fix ? "correction" : "grant",
    source_kind: fix ? "manual" : "achievement",
    source: fix ? "admin" : "achievements",
    label: fix ? null : "Popcorn time",
    reason: fix ? "fix" : null,
    balance: 300 - n,
    level: 2,
    level_up: n === 1,
  };
}
const OPERATIONS = Array.from({ length: 27 }, (_, n) => operation(n + 1));
const seenCursors: string[] = [];

function serve(sent: Array<{ method: string; path: string; body: unknown }>) {
  fake.handler = async (request) => {
    const path = new URL(request.url).pathname;
    if (["PUT", "POST"].includes(request.method)) {
      const body = await request.json();
      sent.push({ method: request.method, path, body });
      if (path.endsWith("/pace")) return json(200, body);
      if (path.endsWith("/streak")) return json(200, body);
      if (path.includes("/rules/") && !path.endsWith("/publish"))
        return json(201, {
          key: "watch",
          version: 1,
          status: "draft",
          event_type: "media.playback_finished",
          definition: body.definition,
        });
      return json(200, {});
    }
    if (path === "/api/v1/admin/gamification/operations") {
      const query = new URL(request.url).searchParams;
      const cursor = query.get("cursor") ?? "";
      const limit = Number(query.get("limit"));
      seenCursors.push(cursor);
      const from = cursor ? Number(cursor) : 0;
      const items = OPERATIONS.slice(from, from + limit);
      const next = from + limit < OPERATIONS.length ? String(from + limit) : null;
      return json(200, { items, next_cursor: next, total: OPERATIONS.length });
    }
    switch (path) {
      case "/api/v1/admin/gamification/pace":
        return json(200, { factor: 1, values: ["xp"] });
      case "/api/v1/admin/gamification/population":
        return json(200, {
          members: [{ user_id: "u1", name: "Ursula", days: 40, xp: 2000, level: 6 }],
          rate_median: 40,
          rate_high: 90,
          active: 3,
        });
      case "/api/v1/admin/gamification/level-curve":
        return json(200, { version: 1, definition: { base: 100, exponent: 1.5 }, preview: [] });
      case "/api/v1/admin/gamification/event-types":
        return json(200, TYPES);
      case "/api/v1/admin/gamification/members/details":
        return json(200, { members: DETAILS });
      case "/api/v1/admin/gamification/members":
        return json(200, { value: "xp", members: MEMBERS });
      case "/api/v1/admin/gamification/progress":
        return json(200, { value: "xp", days: [], members: [], sources: [] });
      case "/api/v1/admin/gamification/level-rewards":
        return json(200, { rewards: [], levels: [] });
      case "/api/v1/admin/gamification/rules":
        return json(200, []);
      case "/api/v1/admin/gamification/streak":
        return json(200, {
          enabled: false,
          event_types: ["media.playback_finished"],
          values: ["xp"],
          tiers: [{ days: 2, multiplier: 1.5 }],
        });
      default:
        return json(200, []);
    }
  };
}

function show(url: string) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <RouterProvider
        router={createMemoryRouter([{ path: "/admin/gamification", element: <GamificationAdmin /> }], {
          initialEntries: [url],
        })}
      />
    </QueryClientProvider>,
  );
}

describe("gamification administration", () => {
  it("sets the overall pace from the progression chart", async () => {
    const sent: Array<{ method: string; path: string; body: unknown }> = [];
    serve(sent);
    show("/admin/gamification?tab=progression");
    const slider = await screen.findByRole("slider", { name: /Overall multiplier/ });
    expect(screen.getByRole("img", { name: /Level reached over time/ })).toBeTruthy();
    fireEvent.change(slider, { target: { value: "1.5" } });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() =>
      expect(sent).toEqual([
        { method: "PUT", path: "/api/v1/admin/gamification/pace", body: { factor: 1.5, values: ["xp"] } },
      ]),
    );
    // the simple mode has no per-action tab
    expect(screen.queryByRole("button", { name: "XP per action" })).toBeNull();
  });

  it("writes a per-action rule from a preset: fixed plus per minute, then publishes it", async () => {
    const sent: Array<{ method: string; path: string; body: unknown }> = [];
    serve(sent);
    show("/admin/gamification?tab=actions&mode=detailed");
    fireEvent.click(await screen.findByRole("button", { name: /Finishing a film or an episode/ }));
    fireEvent.click(await screen.findByRole("button", { name: "Save and publish" }));
    await waitFor(() =>
      expect(sent.map((s) => s.path)).toContain(
        "/api/v1/admin/gamification/rules/finishing_a_film_or_an_episode/publish",
      ),
    );
    const saved = sent[0]?.body as { definition: { grants: Array<Record<string, unknown>> } };
    expect(sent[0]?.path).toBe("/api/v1/admin/gamification/rules/finishing_a_film_or_an_episode");
    expect(saved.definition.grants[0]).toEqual({
      value: "xp",
      amount: 10,
      per_unit: { field: "duration_s", factor: 1 / 60, max: 180 },
    });
  });

  it("saves streak tiers in order", async () => {
    const sent: Array<{ method: string; path: string; body: unknown }> = [];
    serve(sent);
    show("/admin/gamification?tab=streak");
    fireEvent.click(await screen.findByRole("checkbox", { name: "Enable streaks" }));
    fireEvent.click(screen.getByRole("button", { name: "Add a tier" }));
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => expect(sent).toHaveLength(1));
    expect(sent[0]?.body).toMatchObject({
      enabled: true,
      tiers: [
        { days: 2, multiplier: 1.5 },
        { days: 5, multiplier: 2 },
      ],
    });
  });

  it("shows what made every member gain, or one of them", async () => {
    serve([]);
    show("/admin/gamification");
    const member = await screen.findByRole("combobox", { name: "Member" });
    await screen.findByRole("option", { name: "All members (2)" });
    fireEvent.click(screen.getByRole("button", { name: /Show table/ }));
    const table = await screen.findByRole("table", { name: "How members progress" });
    const heads = Array.from(table.querySelectorAll("th")).map((th) => th.textContent);
    expect(heads).toEqual([
      "Day",
      "Plays (films, series, books)",
      "Quests and objectives",
      "Achievements",
      "XP",
    ]);
    expect(table.querySelectorAll("tbody tr")).toHaveLength(2);
    expect(screen.getByText("Running XP of every member")).toBeTruthy();

    fireEvent.change(member, { target: { value: "u1" } });
    await waitFor(() => expect(screen.getByText("Running XP of Noémie")).toBeTruthy());
    const mine = screen.getByRole("table", { name: "How members progress" });
    expect(Array.from(mine.querySelectorAll("th")).map((th) => th.textContent)).toEqual([
      "Day",
      "Plays (films, series, books)",
      "Achievements",
      "XP",
    ]);
    expect(mine.querySelectorAll("tbody tr")).toHaveLength(1);
  });

  it("details every member's XP, levels, Coins and Contribution, or one member's day by day", async () => {
    serve([]);
    show("/admin/gamification");
    const table = await screen.findByRole("table", { name: "Detail by member" });
    expect(table.textContent).toContain("1 → 2 (+1 level)");
    expect(table.textContent).toContain("+25−3· 22 held");
    fireEvent.click(within(table).getByRole("button", { name: "Noémie" }));
    const mine = await screen.findByRole("table", { name: "Detail of Noémie" });
    const rows = Array.from(mine.querySelectorAll("tbody tr")).map((tr) => tr.textContent);
    expect(rows[0]).toContain("level 2");
    expect(rows[0]).toContain("−3");
    expect(rows).toHaveLength(2);
    expect(screen.getByText("Now: level 2 · 120 XP · 22 Coins · 1 Contribution.")).toBeTruthy();
  });

  it("journals every operation in a real table, page by page", async () => {
    serve([]);
    show("/admin/gamification");
    const table = await screen.findByRole("table", { name: "Operations journal" });
    expect(Array.from(table.querySelectorAll("thead th")).map((th) => th.textContent)).toEqual([
      "Date",
      "Member",
      "Amount",
      "Source",
      "Detail",
      "Balance after",
      "Level",
    ]);
    const first = Array.from(table.querySelectorAll("tbody tr")).map((tr) => tr.textContent);
    expect(first).toHaveLength(25);
    expect(first[0]).toContain("+10 XP");
    expect(first[0]).toContain("Level 2 reached");
    expect(screen.getByText("1–25 of 27 operations")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    await waitFor(() => expect(screen.getByText("26–27 of 27 operations")).toBeTruthy());
    const second = Array.from(table.querySelectorAll("tbody tr")).map((tr) => tr.textContent);
    expect(second).toHaveLength(2);
    expect(second[1]).toContain("-2 XP");
    expect(second[1]).toContain("Administration");
    expect(second[1]).toContain("fix");
    expect(screen.getByText("Page 2 of 2")).toBeTruthy();
    expect(seenCursors).toContain("25");
    fireEvent.click(screen.getByRole("button", { name: "Previous" }));
    await waitFor(() => expect(screen.getByText("1–25 of 27 operations")).toBeTruthy());
  });
});
