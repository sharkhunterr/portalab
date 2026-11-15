import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

// issue 462: the video player's settings panel is placed on the whole row of controls, never past its edges —
// anchored on the settings button, it ran past the left edge of a phone (the button sits mid-row there)
const css = readFileSync(
  resolve(dirname(fileURLToPath(import.meta.url)), "../../../src/features/media/player/player.css"),
  "utf8",
);
const rule = (selector: string) =>
  new RegExp(`(^|\\n)${selector.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}\\s*\\{([^}]*)\\}`).exec(css)?.[2] ??
  "";

describe("the player's settings panel", () => {
  it("is placed on the row of controls, not on its button", () => {
    expect(rule(".player-controls")).toMatch(/position:\s*relative/);
    expect(rule(".player-menu-anchor")).toMatch(/position:\s*static/);
  });

  it("is never wider than that row", () => {
    const menu = rule(".player-menu");
    expect(menu).toMatch(/right:\s*0/);
    expect(menu).toMatch(/inline-size:\s*min\([^)]*100%\)/);
    expect(menu).not.toMatch(/100vw/);
  });
});
