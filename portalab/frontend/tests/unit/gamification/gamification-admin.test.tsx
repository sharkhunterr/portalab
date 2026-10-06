import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
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
});
