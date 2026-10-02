import { describe, expect, it } from "vitest";
import { DEFAULT_POLICY, DEFAULT_PREFERENCES } from "../../src/design-system/a11y/preferences";
import { resolve } from "../../src/design-system/themes/apply";
import { BUILTIN_THEMES } from "../../src/design-system/themes/builtin";

// 022 T041 (F8) — a campaign theme overlay applies only when allowed by the preference, never over high
// contrast (accessibility wins), and never when it breaks the accessibility floor.

const overlay = { key: "winter-fest", colors: { accent: "#0b5394", focus: "#0b5394" } };
const options = { overlay, systemReducedMotion: false };

describe("campaign overlay", () => {
  it("applies when allowed", () => {
    const effective = resolve(DEFAULT_PREFERENCES, DEFAULT_POLICY, BUILTIN_THEMES, options);
    expect(effective.overlay).toBe("winter-fest");
    expect(effective.theme.colors.accent).toBe("#0b5394");
  });

  it("is ignored when the user opted out or uses high contrast", () => {
    expect(
      resolve({ ...DEFAULT_PREFERENCES, campaignThemes: "ignore" }, DEFAULT_POLICY, BUILTIN_THEMES, options)
        .overlay,
    ).toBeNull();
    const hc = resolve({ ...DEFAULT_PREFERENCES, contrast: "high" }, DEFAULT_POLICY, BUILTIN_THEMES, options);
    expect(hc.overlay).toBeNull();
    expect(hc.theme.key).toBe("high-contrast");
  });

  it("is ignored when it breaks the floor", () => {
    const unreadable = { key: "pale", colors: { accent: "#eeeeee", accentContrast: "#ffffff" } };
    expect(
      resolve(DEFAULT_PREFERENCES, DEFAULT_POLICY, BUILTIN_THEMES, {
        overlay: unreadable,
        systemReducedMotion: false,
      }).overlay,
    ).toBeNull();
  });

  it("falls back to the default theme when the preferred one is not allowed, keeping the preference", () => {
    const effective = resolve(
      { ...DEFAULT_PREFERENCES, theme: "dark" },
      { ...DEFAULT_POLICY, allowedThemes: ["light"] },
      BUILTIN_THEMES,
      {
        systemReducedMotion: false,
      },
    );
    expect(effective.theme.key).toBe("light");
    expect(effective.requestedTheme).toBe("dark");
    expect(effective.fallback).toBe(true);
  });
});
