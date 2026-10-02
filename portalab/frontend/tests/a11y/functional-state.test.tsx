import { render } from "@testing-library/react";
import axe from "axe-core";
import { describe, expect, it } from "vitest";
import { PreferencesProvider } from "../../src/design-system/a11y/PreferencesProvider";
import { FUNCTIONAL_STATES, FunctionalState, STATE_LABELS } from "../../src/design-system/FunctionalState";
import { BUILTIN_THEMES } from "../../src/design-system/themes/builtin";
import { contrast } from "../../src/design-system/themes/contrast";
import { floorReport } from "../../src/design-system/themes/floor";
import { ThemeProvider } from "../../src/design-system/themes/ThemeProvider";

// 001 T053, updated by 022: every functional state renders a non-color cue (icon + text) and passes axe
// under every built-in theme; every built-in theme passes the WCAG 2.2 AA floor.

describe.each(BUILTIN_THEMES.map((theme) => [theme.key, theme] as const))("%s theme", (key, theme) => {
  it("passes the accessibility floor", () => {
    expect(floorReport(theme).violations).toEqual([]);
  });

  it.each(FUNCTIONAL_STATES)("state %s meets WCAG AA contrast", (state) => {
    expect(contrast(theme.states[state].fg, theme.states[state].bg)).toBeGreaterThanOrEqual(4.5);
  });

  it.each(FUNCTIONAL_STATES)("state %s has icon + text and no axe violation", async (state) => {
    const { container } = render(
      <PreferencesProvider initial={{ theme: key }}>
        <ThemeProvider>
          <main lang="en">
            <FunctionalState state={state} detail="Services" onRetry={() => undefined} />
          </main>
        </ThemeProvider>
      </PreferencesProvider>,
    );
    const element = container.querySelector(`[data-state="${state}"]`) as HTMLElement;
    expect(element.querySelector("svg")).toHaveAttribute("aria-hidden", "true");
    expect(element).toHaveTextContent(STATE_LABELS[state]);
    expect(element.getAttribute("role")).toMatch(/^(status|alert)$/);
    const results = await axe.run(container, { rules: { "color-contrast": { enabled: false } } });
    expect(results.violations.map((v) => v.id)).toEqual([]);
  });
});
