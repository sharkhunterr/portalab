import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { MediaCard, Variant } from "../../../src/features/cards/api";
import { VARIANTS } from "../../../src/features/cards/api";
import { MediaCardView } from "../../../src/features/cards/MediaCardView";

// Issue 295: a card's genre version — its genre's frame (a visual pack's card_frame), foil or not.
const card = {
  id: "c1",
  set: "s1",
  set_code: "HPE",
  set_name: "Harry Potter à l'école des sorciers",
  set_size: 14,
  set_kind: "movie",
  set_family: "fantasy",
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
  it("wears its genre's frame, foil or not", () => {
    expect(shown("genre").dataset.frame).toBe("genre-fantasy");
    expect(shown("genre").dataset.foil).toBeUndefined();
    const foil = shown("genre_foil");
    expect(foil.dataset.frame).toBe("genre-fantasy");
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
