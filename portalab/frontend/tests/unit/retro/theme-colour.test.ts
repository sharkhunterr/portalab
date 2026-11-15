import { afterEach, describe, expect, it, vi } from "vitest";
import { themeHex } from "../../../src/features/retro/RetroPage";

// issue 463: the emulator's buttons and menus in the theme's accent — EmulatorJS reads a « #rrggbb »
describe("the theme's colour for the emulator", () => {
  afterEach(() => vi.restoreAllMocks());

  it("turns what the theme resolves to into #rrggbb", () => {
    vi.spyOn(window, "getComputedStyle").mockReturnValue({
      color: "rgb(31, 79, 209)",
    } as CSSStyleDeclaration);
    expect(themeHex("--player-accent")).toBe("#1f4fd1");
  });

  it("keeps a colour mixed with transparency to its hue", () => {
    vi.spyOn(window, "getComputedStyle").mockReturnValue({
      color: "rgba(255, 204, 0, 0.92)",
    } as CSSStyleDeclaration);
    expect(themeHex("--player-panel")).toBe("#ffcc00");
  });

  it("gives nothing when the theme gives nothing readable: the emulator keeps its own", () => {
    vi.spyOn(window, "getComputedStyle").mockReturnValue({ color: "" } as CSSStyleDeclaration);
    expect(themeHex("--player-stage")).toBeUndefined();
  });
});
