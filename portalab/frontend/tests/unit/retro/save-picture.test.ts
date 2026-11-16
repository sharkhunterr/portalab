import { afterEach, describe, expect, it, vi } from "vitest";
import { contentBox, picture } from "../../../src/features/retro/saves";

// A save's picture is the game's own frame — not the emulator's stage, where on a phone held upright the game
// sits at the top and EmulatorJS 4.2's « canvas » picture showed half of it over a black band.

const w = window as unknown as Record<string, unknown>;
afterEach(() => {
  delete w.EJS_emulator;
  vi.useRealTimers();
});

function image(width: number, height: number, lit: (x: number, y: number) => boolean) {
  const data = new Uint8ClampedArray(width * height * 4);
  for (let y = 0; y < height; y++)
    for (let x = 0; x < width; x++) {
      const i = (y * width + x) * 4;
      const v = lit(x, y) ? 200 : 4;
      data.set([v, v, v, 255], i);
    }
  return { data, width, height };
}

describe("contentBox", () => {
  it("finds the game at the top of a tall stage", () => {
    expect(contentBox(image(8, 20, (_, y) => y < 7))).toEqual({ x: 0, y: 0, width: 8, height: 7 });
  });

  it("finds the game between side bands", () => {
    expect(contentBox(image(20, 6, (x) => x >= 5 && x < 15))).toEqual({ x: 5, y: 0, width: 10, height: 6 });
  });

  it("gives nothing for a black stage", () => {
    expect(contentBox(image(4, 4, () => false))).toBeNull();
  });
});

describe("picture", () => {
  it("asks the core for its frame at the game's own size", async () => {
    const png = new Blob([new Uint8Array([137, 80, 78, 71])], { type: "image/png" });
    const takeScreenshot = vi.fn(async () => ({ blob: png }));
    w.EJS_emulator = { takeScreenshot };
    expect(await picture()).toBe(png);
    expect(takeScreenshot).toHaveBeenCalledWith("retroarch", "png", 0);
  });

  it("takes the bytes a later EmulatorJS answers", async () => {
    w.EJS_emulator = { takeScreenshot: async () => ({ screenshot: new Uint8Array([137, 80, 78, 71]) }) };
    const blob = await picture();
    expect(blob?.type).toBe("image/png");
    expect(blob?.size).toBe(4);
  });

  it("does not wait forever for a core that never answers", async () => {
    vi.useFakeTimers();
    w.EJS_emulator = { takeScreenshot: () => new Promise(() => {}) };
    const taken = picture();
    await vi.advanceTimersByTimeAsync(2500);
    expect(await taken).toBeNull(); // no stage to fall back on here
  });
});
