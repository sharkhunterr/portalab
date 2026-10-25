import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import axe from "axe-core";
import { MemoryRouter } from "react-router";
import { describe, expect, it, vi } from "vitest";

// Issue 253 — the arrival wizard's game: the recommended install (the LAN's game as Portalab ships it, with its
// shop), adjusted, or set by hand; the recommended install applied in one go (what the shop does not sell
// said), then the game's screens tab by tab. Its visual packs install when the portal opens, a few at a time.

const fake = vi.hoisted(() => ({
  handler: (_: Request): Response | Promise<Response> => new Response(null),
}));
vi.mock("../../src/api/client", async (importOriginal) => {
  const { installFakeApi } = await import("../support/fake-api");
  const installed = installFakeApi();
  Object.defineProperty(installed, "handler", { get: () => fake.handler });
  return importOriginal();
});

import { installPacks } from "../../src/features/admin/arrival/ArrivalContinue";
import { GameStep } from "../../src/features/admin/arrival/GameStep";
import { json } from "../support/fake-api";

const COUNTS = {
  catalog: 87,
  packs: 103,
  products: 14,
  settings: 2,
  rules: 16,
  achievements: 66,
  quests: 26,
  campaigns: 3,
  level_rewards: 11,
};

function wrap(node: React.ReactNode) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return (
    <QueryClientProvider client={client}>
      <MemoryRouter>{node}</MemoryRouter>
    </QueryClientProvider>
  );
}

describe("arrival wizard's game", () => {
  it("offers the recommended install, applies it in one go and says what the shop does not sell", async () => {
    const sent: unknown[] = [];
    fake.handler = async (request) => {
      const path = new URL(request.url).pathname;
      if (path === "/api/v1/admin/game/presets") return json(200, [{ key: "lan", counts: COUNTS }]);
      if (path === "/api/v1/admin/game/setup") {
        sent.push(await request.json());
        return json(200, {
          applied: {
            shop: 1300,
            settings: 2,
            curve: 1,
            rules: 16,
            achievements: 66,
            quests: 17,
            campaigns: 3,
          },
          kept: {},
          skipped: [
            { part: "settings", key: "level 10: booster_reserve", reason: "product not in this shop" },
          ],
        });
      }
      return json(200, {});
    };
    const chosen = vi.fn();
    const { container, rerender } = render(
      wrap(<GameStep choice={undefined} onChoose={chosen} settings={<p>the play settings</p>} />),
    );
    const lan = await screen.findByRole("button", {
      name: /^The recommended install\s*The game and the shop.*16 gain rules, 66 achievements.*Portalab's 87 products and 14 products of the LAN, then 103 visual packs installed when the portal opens/,
    });
    expect(screen.getByRole("button", { name: /Set everything myself/ })).toBeInTheDocument();
    const results = await axe.run(container, { rules: { "color-contrast": { enabled: false } } });
    expect(results.violations.map((v) => v.id)).toEqual([]);
    fireEvent.click(lan);
    await vi.waitFor(() => expect(chosen).toHaveBeenCalledWith("lan"));
    expect(sent).toEqual([
      { preset: "lan", parts: ["shop", "settings", "curve", "rules", "achievements", "quests", "campaigns"] },
    ]); // the packs: at the opening
    rerender(wrap(<GameStep choice="lan" onChoose={chosen} settings={<p>the play settings</p>} />));
    expect(
      screen.getByText(/The recommended install is in place.*1300 additions to the shop/),
    ).toBeInTheDocument();
    expect(screen.queryByRole("alert")).toBeNull();
    expect(screen.getByText("the play settings")).toBeInTheDocument();
  });

  it("set by hand: nothing applied, the game's screens tab by tab", async () => {
    const sent: string[] = [];
    fake.handler = (request) => {
      const path = new URL(request.url).pathname;
      if (request.method !== "GET") sent.push(path);
      if (path === "/api/v1/admin/game/presets") return json(200, [{ key: "lan", counts: COUNTS }]);
      return json(200, []);
    };
    const chosen = vi.fn();
    const { rerender } = render(wrap(<GameStep choice={undefined} onChoose={chosen} settings={null} />));
    fireEvent.click(await screen.findByRole("button", { name: /Set everything myself/ }));
    expect(chosen).toHaveBeenCalledWith("custom");
    expect(sent).toEqual([]);
    rerender(wrap(<GameStep choice="custom" onChoose={chosen} settings={<p>the play settings</p>} />));
    for (const tab of ["Levels and unlocks", "Gains and streak", "Achievements", "Quests", "Campaigns"])
      expect(screen.getByRole("button", { name: tab })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Settings" }));
    expect(screen.getByText("the play settings")).toBeInTheDocument();
  });

  it("installs the visual packs at the opening, a few at a time, and says those not installed", async () => {
    const sent: unknown[] = [];
    const packs = ["a", "b", "c", "d", "e", "f", "messenger-bubbles"];
    fake.handler = async (request) => {
      const path = new URL(request.url).pathname;
      if (path === "/api/v1/admin/game/presets") return json(200, [{ key: "lan", counts: COUNTS, packs }]);
      const body = (await request.json()) as { packs: string[] };
      sent.push(body);
      const skipped = body.packs.includes("messenger-bubbles")
        ? [{ part: "packs", key: "pack messenger-bubbles", reason: "ui.visual_pack_blocked" }]
        : [];
      return json(200, { applied: {}, kept: {}, skipped });
    };
    const shares: number[] = [];
    expect(await installPacks((share) => shares.push(share))).toEqual(["messenger-bubbles"]);
    expect(sent).toEqual([
      { preset: "lan", parts: ["packs"], packs: ["a", "b", "c", "d", "e"] },
      { preset: "lan", parts: ["packs"], packs: ["f", "messenger-bubbles"] },
    ]);
    expect(shares.at(-1)).toBe(1);
  });
});
