import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { createMemoryRouter, RouterProvider } from "react-router";
import { describe, expect, it, vi } from "vitest";

// 013 — progression shows XP/level, Contribution and Coins separately; achievements use text states and
// keep hidden ones hidden; the manual grant asks for confirmation above the threshold; anomaly decisions
// need a reason.

const fake = vi.hoisted(() => ({
  handler: (_: Request): Response | Promise<Response> => new Response(null),
}));
vi.mock("../../../src/api/client", async (importOriginal) => {
  const { installFakeApi } = await import("../../support/fake-api");
  const installed = installFakeApi();
  Object.defineProperty(installed, "handler", { get: () => fake.handler });
  return importOriginal();
});

import { AchievementGrid } from "../../../src/features/gamification/achievements/Grid";
import { AnomalyQueue } from "../../../src/features/gamification/admin/AnomalyQueue";
import ProgressionPage from "../../../src/features/gamification/progression/ProgressionPage";
import { json } from "../../support/fake-api";

const PROGRESSION = {
  user_id: "u1",
  xp: 150,
  level: 2,
  level_floor: 100,
  next_level_at: 283,
  contribution: 7,
  coins: 40,
  reserved_coins: 0,
  achievements: 1,
};

function show(element: ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <RouterProvider router={createMemoryRouter([{ path: "/", element }])} />
    </QueryClientProvider>,
  );
}

describe("gamification", () => {
  it("shows the three values separately with the derived level", async () => {
    fake.handler = (request) => {
      const path = new URL(request.url).pathname;
      if (path === "/api/v1/me/progression") return json(200, PROGRESSION);
      if (path === "/api/v1/me/achievements") return json(200, []);
      if (path === "/api/v1/me/quests") {
        return json(200, [
          {
            key: "daily_listen",
            kind: "daily",
            label: "Listen today",
            completed_at: null,
            steps: [{ current: 0, target: 1 }],
            rewards: [{ value: "coins", amount: 10 }],
          },
        ]);
      }
      if (path === "/api/v1/leaderboards/xp") {
        return json(200, { metric: "xp", period: "all", computed_at: null, entries: [], me: null });
      }
      return json(200, {
        items: [
          {
            id: "t1",
            value: "coins",
            delta: -10,
            kind: "spend",
            source_kind: "marketplace",
            rule_key: null,
            rule_version: null,
            reason: "Poster",
            reverses_transaction_id: null,
            occurred_at: "2026-10-01T12:00:00Z",
          },
        ],
        next_cursor: null,
      });
    };
    show(<ProgressionPage />);
    expect(await screen.findByRole("heading", { name: "Level 2" })).toBeTruthy();
    expect(screen.getByText("133 XP to level 3")).toBeTruthy();
    const values = Array.from(document.querySelectorAll(".gamification-values .ds-stat__label")).map(
      (dt) => dt.textContent,
    );
    expect(values).toEqual(["XP", "Contribution", "Coins"]);
    expect(await screen.findByText("Spent")).toBeTruthy();
    expect(screen.getByText("-10 Coins")).toBeTruthy();
    expect(await screen.findByText("You are not ranked yet.")).toBeTruthy();
    expect(await screen.findByText("Listen today")).toBeTruthy();
    expect(screen.getByText("Daily objective · In progress")).toBeTruthy();
    expect(screen.getByText("+10 Coins")).toBeTruthy();
  });

  it("labels achievement states in text and keeps hidden ones hidden", () => {
    show(
      <AchievementGrid
        achievements={[
          { key: "a", state: "unlocked", label: "Rock fan", unlocked_at: "2026-10-01T12:00:00Z" },
          { key: "b", state: "locked", label: "Veteran", progress: [{ current: 2, target: 5 }] },
          { key: "c", state: "hidden" },
        ]}
      />,
    );
    expect(screen.getAllByText("Unlocked")).toHaveLength(2); // its group, and its badge
    expect(screen.getByText("In progress")).toBeTruthy(); // issue 114: the ones started come next
    expect(screen.getByText("Locked")).toBeTruthy();
    expect(screen.getByText("2 / 5")).toBeTruthy();
    // the others are folded away until asked for
    expect(screen.queryByText("Hidden achievement")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Show 1 more achievement" }));
    expect(screen.getByText("Hidden achievement")).toBeTruthy();
  });

  it("requires a reason for anomaly decisions", async () => {
    const posts: string[] = [];
    fake.handler = (request) => {
      if (request.method === "POST") {
        posts.push(new URL(request.url).pathname);
        return json(200, { dropped: 1 });
      }
      return json(200, [
        {
          id: "f1",
          user_id: "u1",
          kind: "grants_per_hour",
          window_start: "2026-10-01T12:00:00Z",
          status: "open",
          withheld: [],
        },
      ]);
    };
    show(<AnomalyQueue />);
    const reject = await screen.findByRole("button", { name: "Reject" });
    expect((reject as HTMLButtonElement).disabled).toBe(true);
    fireEvent.change(screen.getByLabelText("Decision reason"), { target: { value: "Bot traffic" } });
    fireEvent.click(reject);
    await waitFor(() => expect(posts).toEqual(["/api/v1/admin/economy/anomalies/f1/reject"]));
  });
});
