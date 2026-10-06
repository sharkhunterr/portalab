import { describe, expect, it } from "vitest";
import type { Instance } from "../../../src/features/dashboard/api";
import { cellsFor } from "../../../src/features/dashboard/edit/EditSession";
import { collides } from "../../../src/features/dashboard/grid/engine";

// 027 — the cells each screen shows: the desktop coordinates; tablet (8 columns) and phone (4) derived from
// them when the layout is shared; the member's own places when each screen is arranged apart, a widget
// not placed there yet finding a free spot without overlapping the others.

function instance(id: string, cell: { x: number; y: number; w: number; h: number }, views = {}): Instance {
  return {
    id,
    widget_key: `w.${id}`,
    status: "active",
    position: 0,
    ...cell,
    config: {},
    policy: "free",
    locked: false,
    mandatory: false,
    removable: true,
    hideable: true,
    available: true,
    widget: null,
    views,
  } as unknown as Instance;
}

const a = instance("a", { x: 0, y: 0, w: 4, h: 2 }, { phone: { x: 0, y: 5, w: 4, h: 3 } });
const b = instance("b", { x: 4, y: 0, w: 8, h: 2 });

describe("cells of a screen", () => {
  it("derives tablet and phone from the desktop when the layout is shared", () => {
    const phone = cellsFor([a, b], "phone", "shared");
    expect(phone.get("a")).toEqual({ x: 0, y: 0, w: 4, h: 2 }); // a third of the screen or more: full width
    expect(phone.get("b")).toEqual({ x: 0, y: 2, w: 4, h: 2 });
    expect(cellsFor([a, b], "desktop", "shared").get("b")).toEqual({ x: 4, y: 0, w: 8, h: 2 });
  });

  it("keeps each screen's own places and fits newcomers without overlap", () => {
    const phone = cellsFor([a, b], "phone", "per_device");
    expect(phone.get("a")).toEqual({ x: 0, y: 5, w: 4, h: 3 });
    const boxes = [...phone].map(([id, cell]) => ({ id, ...cell }));
    expect(boxes.some((box) => boxes.some((other) => collides(box, other)))).toBe(false);
    expect(Math.max(...boxes.map((box) => box.x + box.w))).toBeLessThanOrEqual(4);
  });
});
