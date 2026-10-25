import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { describe, expect, it, vi } from "vitest";

// issue 248 — a level reached while the member was away is celebrated when they come back, once and on any
// device (the last level seen kept on the server); several levels make one moment, from the first one, with
// each level's rewards and their total.

const fake = vi.hoisted(() => ({
  handler: (_: Request): Response | Promise<Response> => new Response(null),
}));

vi.mock("../../src/api/client", async (importOriginal) => {
  const { installFakeApi } = await import("../support/fake-api");
  const installed = installFakeApi();
  Object.defineProperty(installed, "handler", { get: () => fake.handler });
  return importOriginal();
});

import { PreferencesProvider } from "../../src/design-system/a11y/PreferencesProvider";
import { LevelUpMoment, mergeLevelUps } from "../../src/features/gamification/levelup/LevelUpMoment";
import { json } from "../support/fake-api";

const AWAY = "2026-10-20T10:00:00.000Z";

function portal(celebrated: unknown, saved: unknown[], asked: URL[]) {
  fake.handler = async (request) => {
    const url = new URL(request.url);
    if (url.pathname === "/api/v1/me/preferences") {
      if (request.method === "PUT") {
        saved.push(await request.json());
        return json(200, {});
      }
      return json(200, {
        preferences: celebrated ? [{ key: "shell.levelUp.celebrated", value: celebrated }] : [],
      });
    }
    if (url.pathname === "/api/v1/me/progression") return json(200, { level: 7, xp: 2100 });
    if (url.pathname === "/api/v1/me/level-ups/7") {
      asked.push(url);
      return json(200, {
        level: 7,
        previous: 4,
        xp: 2100,
        level_floor: 2000,
        next_level_at: 2600,
        rewards: [
          { level: 5, coins: 50, contribution: 0, product: null, label: "" },
          { level: 6, coins: 60, contribution: 1, product: null, label: "" },
          { level: 7, coins: 70, contribution: 0, product: "frame_gold", label: "Golden frame" },
        ],
        achievements: [],
      });
    }
    return json(200, []);
  };
  window.localStorage.clear();
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <PreferencesProvider>
          <LevelUpMoment />
        </PreferencesProvider>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("level-ups reached while away", () => {
  it("are celebrated on coming back, in one moment, level by level and in total", async () => {
    const saved: unknown[] = [];
    const asked: URL[] = [];
    portal({ level: 4, at: AWAY }, saved, asked);
    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByText(/3 levels at once/)).toBeTruthy();
    await waitFor(() => expect(within(dialog).getByText("Level by level")).toBeTruthy());
    expect(within(dialog).getByText(/\+180/)).toBeTruthy(); // 50 + 60 + 70 Coins
    expect(within(dialog).getAllByText(/Golden frame/).length).toBeGreaterThan(0);
    expect(asked[0]?.searchParams.get("since")).toBe("4");
    expect(asked[0]?.searchParams.get("after")).toBe(AWAY);
    await act(async () => fireEvent.click(within(dialog).getByRole("button", { name: /continue/i })));
    expect(screen.queryByRole("dialog")).toBeNull();
    await waitFor(() => expect(saved).toHaveLength(1));
    expect((saved[0] as Record<string, { level: number }>)["shell.levelUp.celebrated"]?.level).toBe(7);
  });

  it("start from the current level the first time (nothing to catch up)", async () => {
    const saved: unknown[] = [];
    portal(null, saved, []);
    await waitFor(() => expect(saved).toHaveLength(1));
    expect((saved[0] as Record<string, { level: number }>)["shell.levelUp.celebrated"]?.level).toBe(7);
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("make one moment from the first level when several come before it is closed", () => {
    const first = mergeLevelUps(null, { level: 5, from: 4, xp: 100 });
    expect(mergeLevelUps(first, { level: 6, from: 5, xp: 80 })).toEqual({
      level: 6,
      from: 4,
      xp: 180,
      after: undefined,
    });
    expect(mergeLevelUps(first, { level: 12, preview: "comic" })).toEqual({ level: 12, preview: "comic" });
  });
});
