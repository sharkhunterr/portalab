import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { MediaCard, Variant } from "../../../src/features/cards/api";
import { VARIANTS, variantParts } from "../../../src/features/cards/api";
import { MediaCardView } from "../../../src/features/cards/MediaCardView";

// Issue 295: a card's genre version — its work's main genre's frame (a visual pack's card_frame), foil or not.
const card = {
  id: "c1",
  set: "s1",
  set_code: "HPE",
  set_name: "Harry Potter à l'école des sorciers",
  set_size: 14,
  set_kind: "movie",
  set_family: "fantasy",
  set_genre: "adventure",
  set_edition: "bubble",
  year: 2001,
  number: 2,
  kind: "director",
  person: "p1",
  name: "Chris Columbus",
  flavor: null,
  art: null,
  alt_art: null,
  rarity: "legendary",
  retired: false,
  owned: {},
} as unknown as MediaCard;

function shown(variant: Variant) {
  const { container } = render(<MediaCardView card={card} variant={variant} />);
  return container.querySelector(".mcard") as HTMLElement;
}

describe("a card's genre version", () => {
  it("wears its main genre's frame (not its colour's), foil or not", () => {
    expect(shown("genre").dataset.frame).toBe("genre-adventure");
    expect(shown("genre").dataset.foil).toBeUndefined();
    const foil = shown("genre_foil");
    expect(foil.dataset.frame).toBe("genre-adventure");
    expect(foil.dataset.foil).toBe("true");
  });

  it("its edition's version keeps its edition's frame", () => {
    expect(shown("showcase").dataset.frame).toBe("edition-bubble");
    expect(shown("normal").dataset.frame).toBeUndefined();
  });

  it("comes after the foil, before its edition's, among the versions", () => {
    expect(VARIANTS.slice(0, 5)).toEqual(["normal", "foil", "genre", "genre_foil", "showcase"]);
  });
});

// Issue 296: a booster's signature frame — its scene's card face, worn by the card itself.
describe("a card in its booster's signature frame", () => {
  it("is wrapped in its scene's face for its rarity, foil or not", () => {
    const { container } = render(<MediaCardView card={card} variant="signature_foil:apotheose" />);
    const wrapper = container.querySelector(".mcard-signature") as HTMLElement;
    expect(wrapper.dataset.cardFace).toBe("apotheose-legendary");
    const view = wrapper.querySelector(".mcard") as HTMLElement;
    expect(view.dataset.foil).toBe("true");
    expect(view.dataset.frame).toBeUndefined();
  });

  it("names its version and its frame apart", () => {
    expect(variantParts("signature:geode")).toEqual({ base: "signature", signature: "geode" });
    expect(variantParts("genre_foil")).toEqual({ base: "genre_foil", signature: null });
  });
});
