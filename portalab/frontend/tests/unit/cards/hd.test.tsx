import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { MediaCard } from "../../../src/features/cards/api";
import { MediaCardView } from "../../../src/features/cards/MediaCardView";

// Issue 255: a legendary's HD version — in its edition's frame, foil, its edition's backdrop over the whole
// card: a character without the frame around it, a work borderless.
const card = {
  id: "c1",
  set: "s1",
  set_code: "DUN",
  set_name: "Dune : deuxième partie",
  set_size: 40,
  set_kind: "movie",
  set_family: "sf",
  set_edition: "glass",
  year: 2024,
  number: 7,
  kind: "cast",
  person: "p1",
  name: "Timothée Chalamet",
  role: "Paul Atréides",
  flavor: null,
  art: null,
  alt_art: null,
  rarity: "legendary",
  retired: false,
  owned: {},
} as unknown as MediaCard;

function shown(of: MediaCard, variant: "hd" | "showcase" | "normal") {
  const { container } = render(<MediaCardView card={of} variant={variant} />);
  return container.querySelector(".mcard") as HTMLElement;
}

describe("a card's HD version", () => {
  it("a character: its edition's frame without the frame around it, its backdrop, foil", () => {
    const view = shown(card, "hd");
    expect(view.dataset.frame).toBe("edition-glass");
    expect(view.dataset.hd).toBe("true");
    expect(view.dataset.frameless).toBe("true");
    expect(view.dataset.borderless).toBeUndefined();
    expect(view.dataset.foil).toBe("true");
    expect(view.querySelector(".mcard__backdrop")).not.toBeNull();
  });

  it("a work: borderless, in its edition's frame", () => {
    const view = shown({ ...card, kind: "title", name: "Dune : deuxième partie", role: null }, "hd");
    expect(view.dataset.borderless).toBe("true");
    expect(view.dataset.frameless).toBeUndefined();
    expect(view.dataset.frame).toBe("edition-glass");
  });

  it("no edition, no HD; the other versions keep no backdrop", () => {
    expect(shown({ ...card, set_edition: null }, "hd").dataset.hd).toBeUndefined();
    expect(shown(card, "showcase").querySelector(".mcard__backdrop")).toBeNull();
    expect(shown(card, "normal").dataset.frame).toBeUndefined();
  });
});
