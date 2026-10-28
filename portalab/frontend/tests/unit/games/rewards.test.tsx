import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router";
import { describe, expect, it, vi } from "vitest";

// Issue 265: what the games give, set on the games' page — a rule made in a few choices (here: on the
// podium of the week's board), saved then published as any reward rule; the rules shown in words.

const fake = vi.hoisted(() => ({
  handler: (_: Request): Response | Promise<Response> => new Response(null),
}));
vi.mock("../../../src/api/client", async (importOriginal) => {
  const { installFakeApi } = await import("../../support/fake-api");
  const installed = installFakeApi();
  Object.defineProperty(installed, "handler", { get: () => fake.handler });
  return importOriginal();
});

import { RewardRules } from "../../../src/features/games/RewardRules";
import { json } from "../../support/fake-api";

const PLAYED = {
  key: "games_played",
  version: 1,
  status: "active",
  event_type: "games.played",
  definition: {
    event_type: "games.played",
    label: "A game played",
    predicate: [{ field: "score", op: "gte", value: 500 }],
    grants: [{ value: "xp", amount: 10 }],
    limits: { caps: [{ period: "day", max_amount: 200, value: "xp" }] },
  },
};

function show(sent: Array<{ path: string; body: unknown }>) {
  fake.handler = async (request) => {
    const path = new URL(request.url).pathname;
    if (request.method === "POST") {
      sent.push({ path, body: await request.json().catch(() => null) });
      return json(201, { ...PLAYED, key: path.split("/")[6] });
    }
    if (path === "/api/v1/admin/gamification/rules") return json(200, [PLAYED]);
    return json(200, {});
  };
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <RouterProvider router={createMemoryRouter([{ path: "/", element: <RewardRules /> }])} />
    </QueryClientProvider>,
  );
}

describe("issue 265 — the games' rewards", () => {
  it("makes a rule for the week's podium, then publishes it", async () => {
    const sent: Array<{ path: string; body: unknown }> = [];
    show(sent);
    expect(await screen.findByText("A game played")).toBeTruthy();
    expect(screen.getByText("score ≥ 500")).toBeTruthy();
    expect(screen.getByText("max 200 XP/day")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Add a rule" }));
    fireEvent.click(screen.getByRole("button", { name: /Place on the board/ }));
    fireEvent.change(screen.getByLabelText("Game"), { target: { value: "casting" } });
    fireEvent.change(screen.getByLabelText("Coins"), { target: { value: "20" } });
    fireEvent.click(screen.getByRole("button", { name: "Create the rule" }));
    await waitFor(() => expect(sent).toHaveLength(2));
    expect(sent[1]?.path).toMatch(/\/rules\/games_[a-z0-9_]+\/publish$/);
    const { definition } = sent[0]?.body as { definition: Record<string, unknown> };
    expect(definition).toEqual({
      event_type: "games.board_ranked",
      label: "In the first 3 on the board of the week (The cast)",
      predicate: [
        { field: "game", op: "eq", value: "casting" },
        { field: "period", op: "eq", value: "week" },
        { field: "rank", op: "lte", value: 3 },
      ],
      grants: [
        { value: "xp", amount: 10 },
        { value: "coins", amount: 20 },
      ],
      limits: { caps: [{ period: "day", max_amount: 200, value: "xp" }] },
    });
  });
});
