import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { reducedMotionActive } from "../../src/design-system/a11y/motion";
import { PreferencesProvider } from "../../src/design-system/a11y/PreferencesProvider";
import { DEFAULT_POLICY, DEFAULT_PREFERENCES, sanitize } from "../../src/design-system/a11y/preferences";
import { effectiveTextScale } from "../../src/design-system/a11y/textScale";
import { resolve } from "../../src/design-system/themes/apply";
import { ThemeProvider } from "../../src/design-system/themes/ThemeProvider";
import { BUILTIN_THEMES } from "../support/themes";

// 022 T016 — reduced motion (system and explicit) removes animation; high contrast overrides the theme;
// text scale is bounded 0.85–2.0 and reflows; an admin-forced reduced motion wins.

describe("accessibility preferences", () => {
  it("reduced motion: explicit, system and forced", () => {
    expect(reducedMotionActive("system", DEFAULT_POLICY, true)).toBe(true);
    expect(reducedMotionActive("system", DEFAULT_POLICY, false)).toBe(false);
    expect(reducedMotionActive("on", DEFAULT_POLICY, false)).toBe(true);
    expect(reducedMotionActive("off", DEFAULT_POLICY, true)).toBe(false);
    expect(reducedMotionActive("off", { ...DEFAULT_POLICY, forceReducedMotion: true }, false)).toBe(true);
  });

  it("high contrast overrides the chosen theme while the choice is kept", () => {
    const effective = resolve(
      { ...DEFAULT_PREFERENCES, theme: "dark", contrast: "high" },
      DEFAULT_POLICY,
      BUILTIN_THEMES,
      {
        systemReducedMotion: false,
      },
    );
    expect(effective.theme.key).toBe("high-contrast");
    expect(effective.requestedTheme).toBe("dark");
  });

  it("text scale is clamped to the policy bounds", () => {
    expect(effectiveTextScale(3, DEFAULT_POLICY)).toBe(2);
    expect(effectiveTextScale(0.5, DEFAULT_POLICY)).toBe(0.85);
    expect(effectiveTextScale(1.5, { ...DEFAULT_POLICY, textScaleMax: 1.25 })).toBe(1.25);
  });

  it("applies motion, contrast, density and scale to <html>, content untouched", () => {
    const { getByText } = render(
      <PreferencesProvider
        initial={{ reducedMotion: "on", textScale: 1.5, density: "compact", contrast: "high" }}
      >
        <ThemeProvider>
          <p>Library has 42 items</p>
        </ThemeProvider>
      </PreferencesProvider>,
    );
    const root = document.documentElement;
    expect(root.dataset.reducedMotion).toBe("true");
    expect(root.style.getPropertyValue("--motion-duration-normal")).toBe("0ms");
    expect(root.style.getPropertyValue("--text-scale")).toBe("1.5");
    expect(root.dataset.density).toBe("compact");
    expect(root.dataset.contrast).toBe("high");
    expect(getByText("Library has 42 items")).toBeInTheDocument();
  });

  it("removed or invalid options fall back to defaults (sensible migration)", () => {
    const migrated = sanitize({
      density: "ultra-dense",
      reducedMotion: "on",
      legacyOption: true,
      textScale: "big",
    });
    expect(migrated.density).toBe("comfortable");
    expect(migrated.reducedMotion).toBe("on");
    expect(migrated.textScale).toBe(1);
    expect("legacyOption" in migrated).toBe(false);
  });
});
