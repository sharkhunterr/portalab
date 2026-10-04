import { readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import {
  compact,
  derive,
  firstFree,
  flow,
  type Item,
  move,
  normalize,
  readingOrder,
  resize,
} from "../../src/features/dashboard/grid/engine";

// 027 T065 — the arrangement engine against the cases shared with the backend (arrangement.py).
// UPDATE_ARRANGEMENT_FIXTURES=1 rewrites the expected values (review the diff before committing).

const FILE = join(process.cwd(), "..", "tests", "fixtures", "dashboard-arrangements.json");
interface Case {
  name: string;
  op: string;
  items: Item[];
  id?: string;
  to?: { x: number; y: number };
  size?: { w: number; h: number };
  columns?: number;
  expected?: unknown;
}
const fixtures = JSON.parse(readFileSync(FILE, "utf8")) as { description: string; cases: Case[] };

function run(c: Case): unknown {
  const strip = (items: Item[]) => items.map(({ id, x, y, w, h }) => ({ id, x, y, w, h }));
  switch (c.op) {
    case "compact":
      return strip(compact(c.items));
    case "move":
      return strip(move(c.items, c.id as string, c.to as { x: number; y: number }));
    case "resize":
      return strip(resize(c.items, c.id as string, c.size as { w: number; h: number }));
    case "firstFree":
      return firstFree(c.items, c.size as { w: number; h: number });
    case "normalize":
      return strip(normalize(c.items));
    case "flow":
      return strip(flow(c.items));
    case "derive":
      return strip(derive(c.items, c.columns as number));
    case "readingOrder":
      return readingOrder(c.items).map((i) => i.id);
    default:
      throw new Error(`unknown op ${c.op}`);
  }
}

if (process.env.UPDATE_ARRANGEMENT_FIXTURES) {
  for (const c of fixtures.cases) c.expected = run(c);
  writeFileSync(FILE, `${JSON.stringify(fixtures, null, 1)}\n`);
}

describe("arrangement engine (shared cases)", () => {
  for (const c of fixtures.cases) {
    it(c.name, () => {
      expect(run(c)).toEqual(c.expected);
    });
  }

  it("never leaves overlaps after a move", () => {
    const items: Item[] = [
      { id: "a", x: 0, y: 0, w: 4, h: 2 },
      { id: "b", x: 4, y: 0, w: 4, h: 2 },
      { id: "c", x: 8, y: 0, w: 4, h: 2 },
      { id: "d", x: 0, y: 2, w: 12, h: 1 },
    ];
    for (let x = 0; x <= 8; x += 1) {
      const out = move(items, "d", { x, y: 0 });
      for (const a of out)
        for (const b of out)
          if (a.id < b.id)
            expect(a.x < b.x + b.w && b.x < a.x + a.w && a.y < b.y + b.h && b.y < a.y + a.h).toBe(false);
    }
  });
});
