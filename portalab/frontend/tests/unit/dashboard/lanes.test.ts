import { describe, expect, it } from "vitest";
import { bands, spread } from "../../../src/features/dashboard/grid/engine";

// Issue 235 — on a wide screen the desktop arrangement is cut into bands (runs of rows no widget crosses)
// that stand side by side, each exactly as arranged, under the shortest lane, in reading order.

const item = (id: string, x: number, y: number, w: number, h: number) => ({ id, x, y, w, h });

const home = [
  item("incidents", 0, 0, 3, 1),
  item("campaigns", 3, 0, 3, 1),
  item("progress", 6, 0, 3, 1),
  item("objectives", 9, 0, 3, 1),
  item("continue", 0, 1, 8, 3),
  item("wheel", 8, 1, 4, 3),
  item("calendar", 0, 4, 12, 6),
  item("since", 0, 10, 8, 3),
  item("shuffle", 8, 10, 4, 3),
];

describe("bands", () => {
  it("cuts where no widget crosses from one row to the next", () => {
    expect(bands(home).map((band) => band.map((i) => i.id))).toEqual([
      ["incidents", "campaigns", "progress", "objectives"],
      ["continue", "wheel"],
      ["calendar"],
      ["since", "shuffle"],
    ]);
  });

  it("keeps widgets that overlap rows in one band", () => {
    const tall = [item("a", 0, 0, 6, 4), item("b", 6, 0, 6, 1), item("c", 6, 1, 6, 1), item("d", 0, 4, 12, 1)];
    expect(bands(tall).map((band) => band.map((i) => i.id))).toEqual([["a", "b", "c"], ["d"]]);
  });
});

describe("spread", () => {
  it("puts each band, as arranged, under the shortest lane", () => {
    expect(spread(home, 2)).toEqual([
      item("incidents", 0, 0, 3, 1),
      item("campaigns", 3, 0, 3, 1),
      item("progress", 6, 0, 3, 1),
      item("objectives", 9, 0, 3, 1),
      item("continue", 12, 0, 8, 3),
      item("wheel", 20, 0, 4, 3),
      item("calendar", 0, 1, 12, 6),
      item("since", 12, 3, 8, 3),
      item("shuffle", 20, 3, 4, 3),
    ]);
  });

  it("changes nothing with one lane", () => {
    expect(spread(home, 1)).toEqual(home);
  });
});
