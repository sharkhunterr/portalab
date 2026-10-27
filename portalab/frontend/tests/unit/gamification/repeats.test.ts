import { describe, expect, it } from "vitest";
import { repeats } from "../../../src/features/gamification/admin/repeats";
import type { Operation } from "../../../src/features/gamification/admin/tuning";

// Issue 258: the same gain made again and again is one line of the journal, its amounts added up — issue 261:
// not a sitting (a film, an episode, a session of radio), each its own line.

let n = 0;
function op(at: string, extra: Partial<Operation> = {}): Operation {
  n += 1;
  return {
    id: `op-${n}`,
    occurred_at: at,
    user_id: "jeremie",
    name: "Jérémie",
    value: "xp",
    delta: 5,
    kind: "grant",
    source_kind: "reward_rule",
    source: "quests",
    label: "Objectif du jour",
    reason: null,
    balance: 100 + n,
    level: 5,
    level_up: false,
    play: null,
    title: null,
    other: null,
    bonuses: [],
    ...extra,
  } as Operation;
}

describe("the journal's repeats", () => {
  it("tells a series once, where its latest is, with its total and when it began", () => {
    const rows = [
      op("2026-10-27T15:26:00Z", { bonuses: [{ source: "streak", amount: 2.5, factor: 1.5 }] }),
      op("2026-10-27T15:26:00Z", { value: "coins", delta: 1 }),
      op("2026-10-27T15:20:00Z", { user_id: "beatrice", name: "Béatrice", source: "episode" }),
      op("2026-10-27T15:02:00Z", { bonuses: [{ source: "streak", amount: 2.5, factor: 1.5 }] }),
      op("2026-10-27T15:02:00Z", { value: "coins", delta: 1 }),
      op("2026-10-27T14:47:00Z", { level_up: true, bonuses: [{ source: "streak", amount: 5, factor: 2 }] }),
    ];
    const lines = repeats(rows);
    expect(lines.map((l) => [l.user_id, l.value, l.delta, l.count])).toEqual([
      ["jeremie", "xp", 15, 3],
      ["jeremie", "coins", 2, 2],
      ["beatrice", "xp", 5, 1],
    ]);
    const [xp] = lines;
    expect(xp?.balance).toBe(rows[0]?.balance); // the latest's
    expect(xp?.since).toBe("2026-10-27T14:47:00Z");
    expect(xp?.level_up).toBe(true);
    // the streak's share added up; its multiplier changed along the way, so none is said
    expect(xp?.bonuses).toEqual([{ source: "streak", amount: 10, factor: null }]);
  });

  it("keeps apart what differs: another title, another day", () => {
    const lines = repeats([
      op("2026-10-27T15:00:00Z", { source: "episode", title: "Episode 2" }),
      op("2026-10-27T14:00:00Z", { source: "episode", title: "Episode 1" }),
      op("2026-10-25T12:00:00Z"),
      op("2026-10-24T12:00:00Z"),
    ]);
    expect(lines.map((l) => l.count)).toEqual([1, 1, 1, 1]);
  });
});
