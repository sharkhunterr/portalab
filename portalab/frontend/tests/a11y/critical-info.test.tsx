import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { PreferencesProvider } from "../../src/design-system/a11y/PreferencesProvider";
import { FunctionalState } from "../../src/design-system/state/FunctionalState";
import { contrast } from "../../src/design-system/themes/contrast";
import { floorReport } from "../../src/design-system/themes/floor";
import { CRITICAL_STATES, type ThemeDefinition } from "../../src/design-system/themes/schema";
import { ThemeProvider } from "../../src/design-system/themes/ThemeProvider";
import { BUILTIN_THEMES } from "../support/themes";

// 022 T026 — under every theme and high contrast, critical states stay visible with ≥ 3:1 against the
// surface and a non-color cue; a theme hiding or fading a critical state is rejected by the floor.

describe.each(BUILTIN_THEMES.map((t) => [t.key, t] as const))("%s", (key, theme) => {
  it.each(CRITICAL_STATES)("%s stays visible", (state) => {
    expect(contrast(theme.states[state].fg, theme.colors.surface)).toBeGreaterThanOrEqual(3);
    const { container } = render(
      <PreferencesProvider initial={{ theme: key, contrast: "high" }}>
        <ThemeProvider>
          <FunctionalState state={state} />
        </ThemeProvider>
      </PreferencesProvider>,
    );
    const element = container.querySelector(`[data-state="${state}"]`) as HTMLElement;
    expect(element.querySelector("svg")).not.toBeNull();
    expect(element.textContent?.trim().length).toBeGreaterThan(0);
  });
});

describe("floor rejects hiding critical information", () => {
  const base = structuredClone(BUILTIN_THEMES[0]) as ThemeDefinition;

  it("rejects a hidden or faint critical state", () => {
    const hidden = {
      ...base,
      states: { ...base.states, error: { ...base.states.error, display: "none" as const } },
    };
    expect(floorReport(hidden).violations).toContain("state.error must never be hidden");
    const faint = {
      ...base,
      states: { ...base.states, maintenance: { ...base.states.maintenance, opacity: 0.3 } },
    };
    expect(floorReport(faint).ok).toBe(false);
  });

  it("rejects a low-contrast state color", () => {
    const pale = { ...base, states: { ...base.states, unauthorized: { fg: "#f0d0e0", bg: "#ffffff" } } };
    const report = floorReport(pale);
    expect(report.ok).toBe(false);
    expect(report.violations.some((v) => v.startsWith("state.unauthorized.fg/bg"))).toBe(true);
  });
});
