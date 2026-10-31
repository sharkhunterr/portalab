import { describe, expect, it } from "vitest";
import type { CardPack, PackLook } from "../../../src/features/cards/api";
import { piles } from "../../../src/features/cards/CardBoosters";
import { packBooster } from "../../../src/features/cards/packBooster";

// Issue 293: a bought card booster opens in the scene bound to its product, as in the shop.
const t = ((key: string) => key) as Parameters<typeof packBooster>[0];
const pack = {
  id: "p1",
  source: "shop",
  set: null,
  set_name: null,
  count: 3,
  cards: [],
} as unknown as CardPack;

describe("a card booster's scene", () => {
  it("a bought one: its product's", () => {
    const look = { family: "fantasy", product: "booster-fantasy" } as PackLook;
    expect(packBooster(t, { ...pack, look }, "fr").key).toBe("booster-fantasy");
  });

  it("one given by watching: its own key, the kind's scene", () => {
    expect(packBooster(t, { ...pack, look: null }, "fr").key).toBe("cards:p1");
  });

  // Issue 296: a work of a theme opens in its theme booster's scene; a theme booster is named by its theme.
  it("one given by watching a work of a theme: its theme booster's", () => {
    const look = { family: "family", theme: "anime", product: null } as PackLook;
    expect(packBooster(t, { ...pack, set_name: "One Piece", look }, "fr").key).toBe("cards_theme_anime");
    const bought = { family: "", theme: "kaiju", product: "cards_theme_kaiju" } as unknown as PackLook;
    expect(packBooster(t, { ...pack, look: bought }, "fr").names).toEqual({
      fr: "gamification:cards.theme.kaiju",
      en: "gamification:cards.theme.kaiju",
    });
  });
});

// Issue 297: the same boosters in one pile.
describe("sealed packs in piles", () => {
  it("piles the same product's, and the same content's season, apart", () => {
    const shop = (id: string, product: string) =>
      ({ ...pack, id, look: { product } as PackLook }) as CardPack;
    const content = (id: string, set: string, season: number | null) =>
      ({ ...pack, id, source: "content", set, look: { season } as PackLook }) as CardPack;
    const got = piles([
      shop("a", "sf"),
      content("b", "dune", 1),
      shop("c", "sf"),
      content("d", "dune", 2),
      shop("e", "fantasy"),
    ]);
    expect(got.map((pile) => pile.map((p) => p.id))).toEqual([["a", "c"], ["b"], ["d"], ["e"]]);
  });
});
