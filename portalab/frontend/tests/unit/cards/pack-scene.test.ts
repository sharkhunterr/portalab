import { describe, expect, it } from "vitest";
import type { CardPack } from "../../../src/features/cards/api";
import { packBooster } from "../../../src/features/cards/packBooster";

// Issue 293: a bought card booster opens in the scene bound to its product, as in the shop.
const t = ((key: string) => key) as Parameters<typeof packBooster>[0];
const pack = { id: "p1", source: "shop", set: null, set_name: null, count: 3, cards: [] } as unknown as CardPack;

describe("a card booster's scene", () => {
  it("a bought one: its product's", () => {
    const look = { family: "fantasy", product: "booster-fantasy" } as CardPack["look"];
    expect(packBooster(t, { ...pack, look }, "fr").key).toBe("booster-fantasy");
  });

  it("one given by watching: its own key, the kind's scene", () => {
    expect(packBooster(t, { ...pack, look: null }, "fr").key).toBe("cards:p1");
  });
});
