import { describe, expect, it } from "vitest";
import type { MediaCard } from "../../../src/features/cards/api";
import { figuresOf, runtimeParts } from "../../../src/features/cards/figures";

// Issue 229: the figures printed on a card — the work's own, an unknown one left out.
const base = {
  set_kind: "movie",
  set_facts: { rating: 8.5, votes: 41391, budget: 165_000_000, revenue: 746_606_706, runtime: 169 },
} as unknown as MediaCard;

describe("a card's figures", () => {
  it("a work's card: its rating, its votes, its box office", () => {
    const figures = figuresOf({ ...base, kind: "title" });
    expect(figures.map((f) => f.key)).toEqual(["rating", "votes", "success"]);
    expect(figures[2]?.big.values).toEqual({ ratio: 4.5 });
  });

  it("a role's card: its work's rating and box office", () => {
    expect(figuresOf({ ...base, kind: "cast" }).map((f) => f.key)).toEqual(["rating", "success"]);
  });

  it("a series counts its seasons; an unknown figure is left out", () => {
    const series = { ...base, kind: "cast", set_kind: "series", set_facts: { seasons: 4 } } as MediaCard;
    expect(figuresOf(series).map((f) => f.key)).toEqual(["seasons"]);
    expect(runtimeParts(169)).toEqual({ hours: 2, minutes: "49" });
    expect(runtimeParts(undefined)).toBeNull();
  });
});
