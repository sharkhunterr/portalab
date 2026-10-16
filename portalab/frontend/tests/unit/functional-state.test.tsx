import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { PreferencesProvider } from "../../src/design-system/a11y/PreferencesProvider";
import { FUNCTIONAL_STATES, FunctionalState } from "../../src/design-system/state/FunctionalState";
import type { ThemeDefinition } from "../../src/design-system/themes/schema";
import { ThemeProvider } from "../../src/design-system/themes/ThemeProvider";
import { BUILTIN_THEMES } from "../support/themes";

// 022 T011 — a closed set of ten states; a theme's state map changes color/icon only; the accessible name,
// role and data-state stay identical across themes; unknown states are rejected.

const retro: ThemeDefinition = {
  ...(structuredClone(BUILTIN_THEMES[1]) as ThemeDefinition),
  key: "retro",
  name: "Retro",
  states: Object.fromEntries(
    FUNCTIONAL_STATES.map((state) => [
      state,
      { ...(BUILTIN_THEMES[1] as ThemeDefinition).states[state], icon: "lines" },
    ]),
  ) as ThemeDefinition["states"],
};

function snapshot(themeKey: string, themes: unknown[]) {
  const { container, unmount } = render(
    <PreferencesProvider initial={{ theme: themeKey }} policy={{ allowedThemes: ["light", "dark", "retro"] }}>
      <ThemeProvider themes={themes}>
        {FUNCTIONAL_STATES.map((state) => (
          <FunctionalState key={state} state={state} />
        ))}
      </ThemeProvider>
    </PreferencesProvider>,
  );
  const rows = [...container.querySelectorAll("[data-state]")].map((el) => ({
    state: el.getAttribute("data-state"),
    role: el.getAttribute("role"),
    text: el.textContent,
    icon: el.querySelector("svg")?.getAttribute("data-icon"),
  }));
  unmount();
  return rows;
}

describe("functional states across themes", () => {
  it("has exactly ten states", () => {
    expect(FUNCTIONAL_STATES).toHaveLength(10);
  });

  it("keeps meaning, role and accessible name identical; only presentation changes", () => {
    const themes = [...BUILTIN_THEMES, retro];
    const light = snapshot("light", themes);
    const dark = snapshot("dark", themes);
    const custom = snapshot("retro", themes);
    const meaning = (rows: typeof light) => rows.map(({ state, role, text }) => ({ state, role, text }));
    expect(meaning(dark)).toEqual(meaning(light));
    expect(meaning(custom)).toEqual(meaning(light));
    expect(custom.every((row) => row.icon === "lines")).toBe(true);
    expect(light.find((row) => row.state === "error")?.icon).toBe("warning");
  });

  it("rejects unknown states", () => {
    expect(() => render(<FunctionalState state={"celebrating" as never} />)).toThrow(
      /unknown functional state/,
    );
  });

  it("applies the theme to <html> without touching content", () => {
    render(
      <PreferencesProvider initial={{ theme: "dark" }}>
        <ThemeProvider>
          <p>Data</p>
        </ThemeProvider>
      </PreferencesProvider>,
    );
    expect(document.documentElement.dataset.theme).toBe("dark");
    expect(document.documentElement.style.getPropertyValue("--color-surface")).toBe("#121418");
  });
});
