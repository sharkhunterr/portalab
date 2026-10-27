import { IntlMessageFormat } from "intl-messageformat";
import { describe, expect, it } from "vitest";
import fr from "../../../../backend/locales/fr/gamification.json";
import { reckoning, workOf } from "../../../src/features/gamification/admin/reckoning";
import { repeats } from "../../../src/features/gamification/admin/repeats";
import type { Operation } from "../../../src/features/gamification/admin/tuning";

// Issue 261: a gain says how its rule reckoned it, and the work it was about.

const messages = fr as Record<string, string>;
const t = (id: string, values?: Record<string, string | number>) =>
  String(new IntlMessageFormat(messages[id.replace("gamification:", "")] ?? id, "fr").format(values));
const number = (n: number) => new Intl.NumberFormat("fr").format(n);

function op(extra: Partial<Operation>): Operation {
  return {
    id: "op",
    occurred_at: "2026-10-27T17:45:00Z",
    user_id: "jeremie",
    name: "Jérémie",
    value: "xp",
    delta: 5,
    kind: "grant",
    source_kind: "reward_rule",
    source: "radio",
    label: "Minutes de radio écoutées",
    reason: null,
    balance: 100,
    level: 5,
    level_up: false,
    play: null,
    title: null,
    other: null,
    bonuses: [],
    ...extra,
  } as Operation;
}

const radio = {
  field: "minutes",
  factor: 1 / 3,
  max: 80,
  quantity: 16,
  base: 5,
  multiplier: 1,
  capped: false,
};
const film = {
  field: "watched_s",
  factor: 1 / 60,
  max: 240,
  quantity: 3055.7,
  base: 50,
  multiplier: 1.5,
  capped: false,
};

describe("a gain's reckoning", () => {
  it("tells the radio's minutes and its rate", () => {
    expect(reckoning(op({ reckoning: radio }), t, number)).toBe("16 min × 1 XP / 3 min = 5 XP");
  });

  it("tells a film's minutes, then its streak", () => {
    expect(reckoning(op({ delta: 75, reckoning: film }), t, number)).toBe(
      "50 min × 1 XP/min = 50 XP, × 1,5 avec les bonus = 75 XP",
    );
  });

  it("tells a fixed amount, and a limit that kept some back", () => {
    expect(
      reckoning(op({ delta: 3, reckoning: { fixed: 5, base: 5, multiplier: 1, capped: true } }), t, number),
    ).toBe("5 XP, montant fixe de la règle, ramené à 3 XP par une limite");
  });

  it("says the rate alone for a gain older than its measure kept", () => {
    expect(reckoning(op({ reckoning: { ...radio, quantity: null } }), t, number)).toBe("1 XP / 3 min : 5 XP");
  });
});

describe("a gain's work", () => {
  it("tells an episode by its series, season and number", () => {
    const work = { kind: "episode", title: "Épisode 6", series: "Sissi", season: 2, number: 6 };
    expect(workOf(op({ work }), t)).toEqual({ name: "Sissi · S2 É6", part: null });
    expect(workOf(op({ work: { ...work, title: "La fuite" } }), t)).toEqual({
      name: "Sissi · S2 É6",
      part: "La fuite",
    });
  });

  it("tells a film with its year", () => {
    expect(workOf(op({ work: { kind: "movie", title: "Dune", year: 2021 } }), t)?.name).toBe("Dune (2021)");
  });
});

describe("the journal's lines", () => {
  it("never adds up sessions of radio: each its own line with its own XP", () => {
    const fixed = { fixed: 5, base: 5, multiplier: 1, capped: false };
    const lines = repeats([
      op({ reckoning: radio }),
      op({ id: "b", occurred_at: "2026-10-27T15:26:00Z", reckoning: fixed }),
      op({ id: "c", occurred_at: "2026-10-27T15:02:00Z", reckoning: fixed }),
    ]);
    expect(lines.map((line) => [line.delta, line.count])).toEqual([
      [5, 1],
      [5, 1],
      [5, 1],
    ]);
  });
});
