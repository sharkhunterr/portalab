import { describe, expect, it } from "vitest";
import { floorReport } from "../../../src/design-system/themes/floor";
import { parseTheme } from "../../../src/design-system/themes/schema";
import { formatBytes, severity } from "../../../src/features/admin/ControlCenter";
import { duplicate } from "../../../src/features/appearance/studio/ThemeStudio";
import { BUILTIN_THEMES } from "../../support/themes";

// 027 T096/T094 — a duplicated theme stands on its own (valid, accessible, new key, no family); the Control
// Center ranks problems by impact/criticality and prints sizes for humans.

describe("theme studio", () => {
  const source = BUILTIN_THEMES.find((theme) => theme.family) as (typeof BUILTIN_THEMES)[number];

  it("duplicates a theme into a valid, accessible one with a fresh key and no family", () => {
    const copy = duplicate(source, "Neon Été", new Set([source.key]));
    expect(copy.key).toBe("neon-ete");
    expect(copy.name).toBe("Neon Été");
    expect(copy.family).toBeUndefined();
    expect(parseTheme(copy).errors).toEqual([]);
    expect(floorReport(copy).ok).toBe(true);
    expect(source.family).toBeDefined(); // the original is untouched
  });

  it("never reuses a taken key", () => {
    const copy = duplicate(source, "Orbit", new Set(["orbit", "orbit-2"]));
    expect(copy.key).toBe("orbit-3");
  });
});

describe("control center helpers", () => {
  it("ranks severity from impact and criticality", () => {
    expect(severity(5, 1)).toBe("high");
    expect(severity(1, 3)).toBe("medium");
    expect(severity(1, 2)).toBe("low");
    expect(severity()).toBe("low");
  });

  it("prints sizes for humans", () => {
    expect(formatBytes(512, "en")).toBe("512 B");
    expect(formatBytes(52 * 1024 * 1024, "en")).toBe("52 MB");
    expect(formatBytes(5.8 * 1024 * 1024, "en")).toBe("5.8 MB");
  });
});
