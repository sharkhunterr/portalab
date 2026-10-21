import { describe, expect, it } from "vitest";
import { closeEmptyRows, fillHoles } from "../../../src/features/dashboard/grid/DashboardGrid";

// Issue 12 — a widget hidden while empty gives its place to its neighbour in the same row (the one before
// it, else the one after); a row left with nothing closes up.

const item = (id: string, x: number, y: number, w: number, h: number) => ({ id, x, y, w, h });

describe("fillHoles", () => {
  it("widens the widget before a hidden one, else the one after", () => {
    const since = item("since", 0, 0, 8, 3);
    const shuffle = item("shuffle", 8, 0, 4, 3);
    expect(fillHoles([since], [shuffle])).toEqual([item("since", 0, 0, 12, 3)]);
    const community = item("community", 0, 3, 6, 3);
    const stats = item("stats", 6, 3, 6, 3);
    expect(fillHoles([stats], [community])).toEqual([item("stats", 0, 3, 12, 3)]);
  });

  it("leaves other rows and other heights alone, and a lone hidden row closes", () => {
    const tall = item("tall", 0, 0, 6, 4);
    const gone = item("gone", 6, 0, 6, 3);
    expect(fillHoles([tall], [gone])).toEqual([tall]);
    const below = item("below", 0, 6, 12, 2);
    expect(closeEmptyRows(fillHoles([below], [item("alone", 0, 3, 12, 3)]))).toEqual([
      item("below", 0, 0, 12, 2),
    ]);
  });
});
