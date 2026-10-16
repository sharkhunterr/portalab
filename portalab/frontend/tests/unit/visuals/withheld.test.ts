import { afterEach, describe, expect, it } from "vitest";
import { isWithheld, setWithheld, shownLook } from "../../../src/design-system/visuals/registry";
import { shownEquipped } from "../../../src/features/community/profile/looks";

/** 028: the looks of one of Portalab's own packs switched off show the default — the choice is kept. */
describe("visual packs — withheld looks", () => {
  afterEach(() => setWithheld({}));

  it("knows which looks a switched-off pack holds", () => {
    setWithheld({ avatar_frame: ["runes"], theme: ["wizard"] });
    expect(isWithheld("avatar_frame", "runes")).toBe(true);
    expect(isWithheld("avatar_frame", "gold")).toBe(false);
    expect(isWithheld("profile_banner", "runes")).toBe(false);
    expect(shownLook("level_up", "spell", "theme")).toBe("spell");
    setWithheld({ level_up: ["spell"] });
    expect(shownLook("level_up", "spell", "theme")).toBe("theme");
  });

  it("shows the default for what a member wears from a switched-off pack, and keeps the rest", () => {
    setWithheld({ avatar_frame: ["runes"], profile_banner: ["castle"] });
    const shown = shownEquipped({ frame: "runes", banner: "castle", name: "wizard", level: "crest" });
    expect(shown).toEqual({ frame: null, banner: null, name: "wizard", level: "crest" });
    setWithheld({});
    expect(shownEquipped({ frame: "runes" }).frame).toBe("runes"); // back when the pack is
  });
});
