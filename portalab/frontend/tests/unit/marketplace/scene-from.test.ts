import { describe, expect, it } from "vitest";
import type { ExternalElement } from "../../../src/design-system/visuals/registry";
import { bindingOf, sceneFrom } from "../../../src/features/marketplace/boosters/scene/scene";

// issue 154 — the Test step rebuilds a scene from its version's own elements (its parts by their folder);
// issue 153 — a booster wears its own scene, else the one every booster wears.

const element = (type: string, look: string, folder: string, extra: Partial<ExternalElement> = {}) =>
  ({
    pack: "maree",
    sha: "x",
    product: "",
    type,
    look,
    kind: "css",
    names: {},
    folder,
    ...extra,
  }) as ExternalElement;

describe("scenes", () => {
  it("finds a scene's parts by their folder, per rarity too", () => {
    const back = element("card_back", "maree", "back-maree");
    const face = element("card_face", "maree-epic-face", "face-epic");
    const look = element("booster_look", "maree", "look-maree");
    const scene = element("booster_scene", "maree", "scene-maree", {
      parts: {
        booster_look: "look-maree",
        back: { common: "back-maree" },
        face: { epic: "elements/face-epic" },
      },
    });
    const built = sceneFrom([back, face, look, scene], scene);
    expect(built.look).toBe("maree");
    expect(built.parts.booster_look).toBe(look);
    expect(built.parts.back?.common).toBe(back);
    expect(built.parts.face?.epic).toBe(face);
    expect(built.parts.opening).toBeUndefined();
  });

  it("a booster's own scene, else every booster's", () => {
    const all = { pack: "maree", look: "maree", names: {}, booster_look: "maree" };
    const own = { ...all, look: "other" };
    expect(bindingOf({ "*": all, booster_x: own }, "booster_x")).toBe(own);
    expect(bindingOf({ "*": all }, "booster_y")).toBe(all);
    expect(bindingOf({}, "booster_y")).toBeUndefined();
  });
});
