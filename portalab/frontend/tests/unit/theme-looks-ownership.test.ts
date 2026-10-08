import { describe, expect, it } from "vitest";
import { DEFAULT_PREFERENCES } from "../../src/design-system/a11y/preferences";
import { type Effective, FREE_LOOKS, resolveLooks } from "../../src/design-system/themes/apply";
import { builtinTheme } from "../../src/design-system/themes/builtin";
import type { ThemeDefinition } from "../../src/design-system/themes/schema";

// 027 — a universe theme alone brings its colours, layout and words; its sold looks (ambience,
// notifications, celebration, level-up) are worn with its universe's pack, else the free defaults show.

const effective = (key: string): Effective => {
  const theme = builtinTheme(key) as ThemeDefinition;
  return {
    theme,
    scheme: theme.colorScheme,
    requestedTheme: key,
    fallback: false,
    reducedMotion: false,
    textScale: 1,
    overlay: null,
  };
};
const following = {
  ...DEFAULT_PREFERENCES,
  ambient: "theme",
  notificationStyle: "theme",
  notificationAnimation: "theme",
  celebration: "theme",
  levelUp: "theme",
} as typeof DEFAULT_PREFERENCES;

describe("a theme's own looks need the member to own them", () => {
  it("shows the theme's looks when nothing is withheld", () => {
    const looks = resolveLooks(effective("upsidedown"), following, {});
    expect(looks).toMatchObject({
      ambient: "upsidedown",
      notificationStyle: "upsidedown",
      levelUp: "upsidedown",
    });
  });

  it("falls back to the free defaults for the looks the member does not own", () => {
    const locked = {
      ambient: new Set(["upsidedown"]),
      notificationStyle: new Set(["upsidedown"]),
      notificationAnimation: new Set(["flipup"]),
      celebration: new Set(["flicker"]),
      levelUp: new Set(["upsidedown"]),
    };
    expect(resolveLooks(effective("upsidedown"), following, locked)).toEqual(FREE_LOOKS);
  });

  it("waits with the free defaults while ownership is not known", () => {
    expect(resolveLooks(effective("upsidedown"), following, null)).toEqual(FREE_LOOKS);
  });

  it("keeps the member's own choices (checked when saved) whatever the theme", () => {
    const chosen = { ...following, ambient: "snow" } as typeof DEFAULT_PREFERENCES;
    const looks = resolveLooks(effective("upsidedown"), chosen, { ambient: new Set(["upsidedown"]) });
    expect(looks.ambient).toBe("snow");
  });
});
