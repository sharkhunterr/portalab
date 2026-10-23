import { describe, expect, it } from "vitest";
import type { MediaCard } from "../../../src/features/cards/api";
import { gaugesOf } from "../../../src/features/cards/gauges";

// Issue 229: a card's gauges — the work's own figures on fixed scales, nothing a server holds.
const base = {
  id: "c",
  set: "s",
  set_code: "INT",
  set_name: "Interstellar",
  set_size: 15,
  set_kind: "movie",
  year: 2014,
  number: 1,
  person: null,
  name: "Interstellar",
  role: null,
  flavor: null,
  art: null,
  alt_art: null,
  rarity: "legendary",
  retired: false,
  owned: {},
  set_facts: { rating: 8.5, votes: 41391, budget: 165_000_000, revenue: 746_606_706 },
} satisfies Partial<MediaCard>;

describe("a card's gauges", () => {
  it("a film: its rating, popularity and success", () => {
    const [rating, votes, success] = gaugesOf({ ...base, kind: "title" } as MediaCard);
    expect(rating?.filled).toBe(9); // 8.5 / 10
    expect(votes?.filled).toBe(10); // 41 391 votes: near the top of 100…50 000
    expect(success?.filled).toBe(7); // ×4.5, on ×1…×10
    expect(success?.value?.values).toEqual({ ratio: 4.5 });
  });

  it("a role: its place in the credits, then its work's", () => {
    const gauges = gaugesOf({ ...base, kind: "cast", billing: 2 } as MediaCard);
    expect(gauges.map((g) => g.key)).toEqual(["billing", "work", "success"]);
    expect(gauges[0]?.filled).toBe(8);
    expect(gauges[0]?.value?.values).toEqual({ place: 3 });
  });

  it("an unknown figure stays empty, a series counts its seasons", () => {
    const gauges = gaugesOf({
      ...base,
      kind: "title",
      set_kind: "series",
      set_facts: { seasons: 4 },
    } as MediaCard);
    expect(gauges[0]?.filled).toBeNull();
    expect(gauges[0]?.value).toBeNull();
    expect(gauges[2]).toMatchObject({ key: "seasons", filled: 4 });
  });
});
