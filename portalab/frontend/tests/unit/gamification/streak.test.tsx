import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";

// 027 — a play streak drawn as a card (its flame, today's state, its road to the tiers, its last fourteen
// days, its record, its freezes) and, for the administrators, every member's streak.

const fake = vi.hoisted(() => ({
  handler: (_: Request): Response | Promise<Response> => new Response(null),
}));
vi.mock("../../../src/api/client", async (importOriginal) => {
  const { installFakeApi } = await import("../../support/fake-api");
  const installed = installFakeApi();
  Object.defineProperty(installed, "handler", { get: () => fake.handler });
  return importOriginal();
});

import { MemberStreaks } from "../../../src/features/gamification/admin/MemberStreaks";
import { StreakCard } from "../../../src/features/gamification/progression/StreakCard";
import { json } from "../../support/fake-api";

const RECENT = [
  { day: "2026-10-27", state: "missed" },
  { day: "2026-10-28", state: "missed" },
  { day: "2026-10-29", state: "missed" },
  { day: "2026-10-30", state: "missed" },
  { day: "2026-10-31", state: "done" },
  { day: "2026-11-01", state: "done" },
  { day: "2026-11-02", state: "done" },
  { day: "2026-11-03", state: "done" },
  { day: "2026-11-04", state: "done" },
  { day: "2026-11-05", state: "missed" },
  { day: "2026-11-06", state: "missed" },
  { day: "2026-11-07", state: "done" },
  { day: "2026-11-08", state: "frozen" },
  { day: "2026-11-09", state: "pending" },
];
const STREAK = {
  enabled: true,
  days: 3,
  multiplier: 1.5,
  next: { days: 5, multiplier: 2 },
  tiers: [
    { days: 2, multiplier: 1.5 },
    { days: 5, multiplier: 2 },
  ],
  today: false,
  best: 5,
  last_day: "2026-11-08",
  recent: RECENT,
  freezes: 2,
  last_frozen: "2026-11-08",
};

function show(element: ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}>{element}</QueryClientProvider>);
}

describe("play streaks", () => {
  it("draws my streak: its days, today still to come, its road, its last days and its record", async () => {
    fake.handler = (request) =>
      new URL(request.url).pathname === "/api/v1/me/streak" ? json(200, STREAK) : json(404, {});
    show(<StreakCard />);
    expect(await screen.findByRole("heading", { name: "3 days in a row" })).toBeTruthy();
    expect(screen.getByText(/Today does not count yet/)).toBeTruthy();
    expect(screen.getByText("×1.5", { selector: ".streak-card__multiplier" })).toBeTruthy();
    const road = screen.getByRole("progressbar", { name: "Streak progress" });
    expect(road.getAttribute("aria-valuenow")).toBe("3");
    expect(road.getAttribute("aria-valuemax")).toBe("5");
    expect(screen.getByText("Day 3 of 5 · ×2 at the end")).toBeTruthy();
    const badges = within(road).getAllByText(/^×/);
    expect(badges.map((b) => [b.textContent, b.parentElement?.dataset.reached])).toEqual([
      ["×1", "true"],
      ["×1.5", "true"],
      ["×2", undefined],
    ]);
    const days = within(screen.getByRole("list", { name: "Last 14 days" })).getAllByRole("listitem");
    expect(days.map((d) => d.dataset.state).slice(-3)).toEqual(["done", "frozen", "pending"]);
    // the strip says what it is: my last days, the active ones counted, today named
    expect(screen.getByText("My last 14 days")).toBeTruthy();
    expect(screen.getByText(/7 active days out of 14/)).toBeTruthy();
    expect(within(days.at(-1) as HTMLElement).getByText(/^Today, /)).toBeTruthy();
    expect(days.at(-1)?.querySelector("[data-today]")).toBeTruthy();
    expect(screen.getByText("5 days")).toBeTruthy(); // the record
    expect(screen.getByText("Record")).toBeTruthy();
  });

  it("says nothing while streaks are switched off", async () => {
    fake.handler = () => json(200, { ...STREAK, enabled: false });
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const { container } = render(
      <QueryClientProvider client={client}>
        <StreakCard />
      </QueryClientProvider>,
    );
    await new Promise((resolve) => setTimeout(resolve, 20));
    expect(container.querySelector(".streak-card")).toBeNull();
  });

  it("lists every member's streak for the administrators", async () => {
    fake.handler = (request) =>
      new URL(request.url).pathname === "/api/v1/admin/gamification/streaks"
        ? json(200, [
            { ...STREAK, user_id: "u1", name: "Ursula", today: true },
            { ...STREAK, user_id: "u2", name: "Ulrich", days: 0, multiplier: 1, best: 2, freezes: 0 },
          ])
        : json(404, {});
    show(<MemberStreaks />);
    const table = await screen.findByRole("table", { name: "Members' streaks" });
    const rows = within(table).getAllByRole("row").slice(1);
    expect(within(rows[0] as HTMLElement).getByText("Ursula")).toBeTruthy();
    expect(within(rows[0] as HTMLElement).getByText("counted")).toBeTruthy();
    expect(within(rows[1] as HTMLElement).getByText("Ulrich")).toBeTruthy();
  });
});
