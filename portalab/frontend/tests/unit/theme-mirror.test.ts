import { afterEach, describe, expect, it } from "vitest";
import { applyFirstPaint } from "../../src/design-system/themes/firstPaint";
import { mirroredTheme, mirrorTheme } from "../../src/design-system/themes/mirror";
import { builtinTheme } from "../support/themes";

// 028: only the socle's interfaces ship in the code — the one last applied is mirrored in the browser, so the
// first paint draws a universe before the server answers; a broken mirror leaves the socle's default.

afterEach(() => {
  window.localStorage.clear();
  delete document.documentElement.dataset.theme;
});

describe("the interface mirrored for the first paint", () => {
  it("draws the member's interface before the server answers", () => {
    const matrix = builtinTheme("matrix");
    expect(matrix).toBeDefined();
    mirrorTheme(matrix as NonNullable<typeof matrix>);
    expect(mirroredTheme()?.key).toBe("matrix");
    window.localStorage.setItem("portalab.ui", JSON.stringify({ preferences: { theme: "matrix" } }));
    applyFirstPaint();
    expect(document.documentElement.dataset.theme).toBe("matrix");
  });

  it("keeps the socle's default when the mirror is broken", () => {
    window.localStorage.setItem("portalab.theme", "{not json");
    expect(mirroredTheme()).toBeUndefined();
    applyFirstPaint();
    expect(document.documentElement.dataset.theme).toBe("portalab-dark");
  });
});
