import { describe, expect, it } from "vitest";
import { DEFAULT_POLICY, DEFAULT_PREFERENCES } from "../../src/design-system/a11y/preferences";
import { applyToDocument, resolve } from "../../src/design-system/themes/apply";
import { BUILTIN_THEMES, builtinTheme } from "../../src/design-system/themes/builtin";
import { floorReport } from "../../src/design-system/themes/floor";
import { parseTheme, presentationOf, THEME_SCHEMA_VERSION } from "../../src/design-system/themes/schema";

// 027 T005 — theme v2: layout/motion/sound vocabulary (incl. principle-changing arrangements), refusal of
// unknown values with their path, v1 upgrade with defaults, families resolved by the color mode.

const v1 = () => structuredClone(builtinTheme("light")) as Record<string, unknown>;
const portalab = () => structuredClone(builtinTheme("portalab-dark")) as Record<string, unknown>;

describe("theme schema v2", () => {
  it("accepts every arrangement the portal implements, including footer header and orbit navigation", () => {
    const theme = {
      ...portalab(),
      key: "orbit-test",
      layout: {
        nav: { desktop: "orbit", tablet: "orbit", phone: "orbit" },
        header: "compact",
        headerPosition: "bottom",
        cards: "outlined",
        content: "narrow",
        corners: "square",
        widgetFrame: "plain",
      },
      motion: { profile: "playful", celebration: "glow" },
    };
    const { theme: parsed, errors } = parseTheme(theme);
    expect(errors).toEqual([]);
    const presentation = presentationOf(parsed as never);
    expect(presentation.nav).toEqual({ desktop: "orbit", tablet: "orbit", phone: "orbit" });
    expect(presentation.headerPosition).toBe("bottom");
    expect(presentation.motion).toBe("playful");
  });

  it("refuses an arrangement the portal does not offer, naming the path", () => {
    const errors = parseTheme({ ...portalab(), layout: { nav: { desktop: "floating" } } }).errors;
    expect(errors.join()).toMatch(/layout\.nav\.desktop/);
    expect(parseTheme({ ...portalab(), layout: { grid: "masonry" } }).errors.length).toBeGreaterThan(0);
    expect(parseTheme({ ...portalab(), sounds: { boom: "asset:x.wav" } }).errors.length).toBeGreaterThan(0);
  });

  it("upgrades a v1 document and fills the presentation defaults", () => {
    const { theme, errors } = parseTheme(v1());
    expect(errors).toEqual([]);
    expect(theme?.schemaVersion).toBe(THEME_SCHEMA_VERSION);
    expect(presentationOf(theme as never)).toMatchObject({
      nav: { desktop: "sidebar", tablet: "rail", phone: "drawer" },
      header: "full",
      headerPosition: "top",
      cards: "elevated",
      motion: "subtle",
    });
  });

  it("built-in themes pass the floor, including gamification accents", () => {
    for (const theme of BUILTIN_THEMES) {
      expect(floorReport(theme).violations).toEqual([]);
    }
  });

  it("resolves the default family to its dark member, light on request, device on system", () => {
    const policy = DEFAULT_POLICY;
    expect(resolve(DEFAULT_PREFERENCES, policy, BUILTIN_THEMES).theme.key).toBe("portalab-dark");
    const light = { ...DEFAULT_PREFERENCES, colorMode: "light" as const };
    expect(resolve(light, policy, BUILTIN_THEMES).theme.key).toBe("portalab-light");
    const system = { ...DEFAULT_PREFERENCES, colorMode: "system" as const };
    expect(resolve(system, policy, BUILTIN_THEMES, { systemDark: false }).theme.key).toBe("portalab-light");
    const explicit = { ...DEFAULT_PREFERENCES, theme: "dark" };
    expect(resolve(explicit, policy, BUILTIN_THEMES).theme.key).toBe("dark");
  });

  it("writes the arrangement attributes on the root, accessibility last", () => {
    const root = document.createElement("html");
    const effective = resolve(DEFAULT_PREFERENCES, DEFAULT_POLICY, BUILTIN_THEMES);
    applyToDocument(effective, DEFAULT_PREFERENCES, root);
    expect(root.dataset).toMatchObject({ navPhone: "drawer", headerPosition: "top", cards: "glass" });
    expect(root.dataset.motion).toBe("lively");
    applyToDocument({ ...effective, reducedMotion: true }, DEFAULT_PREFERENCES, root);
    expect(root.dataset.motion).toBe("none");
    expect(root.dataset.celebration).toBe("none");
  });
});
