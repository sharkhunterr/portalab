import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import axe from "axe-core";
import { MemoryRouter } from "react-router";
import { describe, expect, it, vi } from "vitest";

// Issue 253 — the arrival wizard's game: the recommended install (the LAN's game as Portalab ships it, with its
// shop), adjusted, or set by hand. Recommended, it is only chosen: the portal's opening puts it in place, part
// after part, its visual packs a few at a time. Adjusted, it is put in place at once, part after part (what the
// shop does not sell said), then the game's screens tab by tab.

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
import { applyGame, GameStep, notApplied } from "../../src/features/admin/arrival/GameStep";
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

const NONE = { shop: 0, packs: 0, settings: 0, curve: 0, rules: 0, achievements: 0, quests: 0, campaigns: 0 };

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
  it("offers the recommended install and only records it: the opening puts it in place", async () => {
    const sent: string[] = [];
    fake.handler = (request) => {
      const path = new URL(request.url).pathname;
      if (request.method !== "GET") sent.push(path);
      if (path === "/api/v1/admin/game/presets") return json(200, [{ key: "lan", counts: COUNTS }]);
      return json(200, {});
    };
    const chosen = vi.fn();
    const { container, rerender } = render(
      wrap(<GameStep choice={undefined} onChoose={chosen} settings={<p>the play settings</p>} />),
    );
    const lan = await screen.findByRole("button", {
      name: /^The recommended install\s*The game and the shop.*16 gain rules, 66 achievements.*Portalab's 87 products and 14 products of the LAN; 103 visual packs/,
    });
    expect(screen.getByRole("button", { name: /Set everything myself/ })).toBeInTheDocument();
    const results = await axe.run(container, { rules: { "color-contrast": { enabled: false } } });
    expect(results.violations.map((v) => v.id)).toEqual([]);
    fireEvent.click(lan);
    expect(chosen).toHaveBeenCalledWith("lan");
    expect(sent).toEqual([]); // nothing to wait for here
    rerender(wrap(<GameStep choice="lan" onChoose={chosen} settings={<p>the play settings</p>} />));
    expect(screen.getByText(/will be put in place when the portal opens/)).toBeInTheDocument();
    expect(screen.getByText("the play settings")).toBeInTheDocument();
  });

  it("adjusted: put in place part after part, what the shop does not sell said", async () => {
    const sent: unknown[] = [];
    let release = () => {};
    const held = new Promise<void>((resolve) => {
      release = resolve;
    });
    fake.handler = async (request) => {
      const path = new URL(request.url).pathname;
      if (path === "/api/v1/admin/game/presets") return json(200, [{ key: "lan", counts: COUNTS }]);
      if (path === "/api/v1/admin/game/setup") {
        const body = (await request.json()) as { parts: string[] };
        sent.push(body);
        const shop = body.parts.includes("shop");
        if (shop) await held; // the shop takes its time: its progress shown meanwhile
        const play = body.parts.includes("settings");
        return json(200, {
          applied: { ...NONE, ...(shop ? { shop: 1300 } : play ? { rules: 16 } : { achievements: 66 }) },
          kept: {},
          skipped: play
            ? [{ part: "settings", key: "level 10: booster_reserve", reason: "product not in this shop" }]
            : [],
        });
      }
      return json(200, []);
    };
    const chosen = vi.fn();
    const { rerender } = render(wrap(<GameStep choice={undefined} onChoose={chosen} settings={null} />));
    fireEvent.click(await screen.findByRole("button", { name: /The recommended install, adjusted/ }));
    expect(
      await screen.findByText(/Putting the game and the shop in place: Setting up the shop \(1\/4\)/),
    ).toBeInTheDocument();
    release();
    await vi.waitFor(() => expect(chosen).toHaveBeenCalledWith("tune"));
    expect(sent).toEqual([
      { preset: "lan", parts: ["shop"] },
      { preset: "lan", parts: ["settings", "curve", "rules"] },
      { preset: "lan", parts: ["achievements", "quests"] },
      { preset: "lan", parts: ["campaigns"] },
    ]);
    rerender(wrap(<GameStep choice="tune" onChoose={chosen} settings={null} />));
    expect(screen.getByText(/1300 additions to the shop/)).toBeInTheDocument();
    expect(screen.getByText(/booster_reserve/)).toBeInTheDocument();
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("a part applied at the opening says what it could not put in place", async () => {
    fake.handler = () =>
      json(200, {
        applied: { campaigns: 2 },
        kept: {},
        skipped: [
          { part: "campaigns", key: "summer", reason: "invalid" },
          { part: "settings", key: "level 3: x", reason: "product not in this shop" },
        ],
      });
    expect(notApplied(await applyGame("campaigns"))).toEqual(["campaigns summer"]);
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
