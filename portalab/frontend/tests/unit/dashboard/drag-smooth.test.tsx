import { fireEvent, render } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { AnnounceProvider } from "../../../src/design-system/a11y/Announce";
import type { Instance } from "../../../src/features/dashboard/api";
import { DashboardGrid } from "../../../src/features/dashboard/grid/DashboardGrid";

// Issue 496 — arranging the dashboard lagged on an older phone: every pointer move re-rendered every widget.
// The moved widget now follows the pointer on its own element, once a frame; the grid renders again only when
// the widget reaches another cell.

function instance(id: string, cell: { x: number; y: number; w: number; h: number }): Instance {
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
    views: {},
  } as unknown as Instance;
}

const a = instance("a", { x: 0, y: 0, w: 4, h: 2 });
const b = instance("b", { x: 4, y: 0, w: 4, h: 2 });
const frames: FrameRequestCallback[] = [];

beforeEach(() => {
  vi.stubGlobal("requestAnimationFrame", (callback: FrameRequestCallback) => frames.push(callback));
  vi.stubGlobal("cancelAnimationFrame", () => undefined);
  // 12 columns of 100 px (no gap), rows of 76 px
  vi.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockReturnValue({ width: 1200 } as DOMRect);
  HTMLElement.prototype.setPointerCapture = () => undefined;
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  frames.length = 0;
});

describe("arranging the dashboard (issue 496)", () => {
  it("moves a widget without rendering the grid at every pointer move", () => {
    const renders: string[] = [];
    const move = vi.fn();
    const arranger = { move, resize: vi.fn(), preview: () => null };
    const cells = new Map([
      ["a", { x: 0, y: 0, w: 4, h: 2 }],
      ["b", { x: 4, y: 0, w: 4, h: 2 }],
    ]);
    const { container } = render(
      <AnnounceProvider>
        <DashboardGrid
          label="Dashboard"
          instances={[a, b]}
          cells={cells}
          columns={12}
          arranger={arranger}
          render={(item, handles) => {
            renders.push(item.id ?? "");
            return <div>{handles}</div>;
          }}
        />
      </AnnounceProvider>,
    );
    const grip = container.querySelectorAll<HTMLElement>(".dash-grip")[0] as HTMLElement;
    const cell = grip.closest<HTMLElement>(".dashboard-grid__cell") as HTMLElement;

    fireEvent.pointerDown(grip, { button: 0, clientX: 10, clientY: 10, pointerId: 1 });
    const started = renders.length;
    for (const x of [20, 30, 40, 50]) fireEvent.pointerMove(grip, { clientX: x, clientY: 10, pointerId: 1 });
    expect(renders.length).toBe(started); // still in its cell: nothing rendered again
    for (const frame of frames.splice(0)) frame(0);
    expect(cell.style.transform).toBe("translate(40px, 0px)"); // the widget follows the pointer

    fireEvent.pointerMove(grip, { clientX: 220, clientY: 10, pointerId: 1 }); // two cells on
    expect(renders.length).toBeGreaterThan(started); // the placeholder and the neighbours move
    fireEvent.pointerUp(grip, { clientX: 220, clientY: 10, pointerId: 1 });
    expect(move).toHaveBeenCalledWith("a", 2, 0);
    expect(cell.style.transform).toBe("");
  });
});
