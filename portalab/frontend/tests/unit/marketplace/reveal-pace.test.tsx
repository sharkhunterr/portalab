import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, fireEvent, render } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  BoosterReveal,
  demoBooster,
  demoCards,
} from "../../../src/features/marketplace/boosters/BoosterReveal";

// Issue 255: « reveal all » turns one card after the other and leaves each to be read — the next never turns
// while the one before is still turning or just turned.

function stage() {
  const cards = demoCards((rarity) => rarity);
  render(
    <QueryClientProvider client={new QueryClient()}>
      <BoosterReveal
        booster={demoBooster({ en: "Try" }, cards.length)}
        demo={{ cards, scene: null }}
        onClose={() => {}}
      />
    </QueryClientProvider>,
  );
  const states = () =>
    [...document.querySelectorAll<HTMLElement>(".booster-card")].map((card) => card.dataset.state);
  return { states };
}

const advance = (ms: number) => act(() => vi.advanceTimersByTime(ms));

describe("revealing all the cards", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    // jsdom draws no layout: the row has nothing to scroll
    HTMLElement.prototype.scrollTo = () => {};
  });
  afterEach(() => vi.useRealTimers());

  it("leaves each card turned for a while before the next", () => {
    const { states } = stage();
    fireEvent.click(document.querySelector(".booster-stage__tear") as HTMLElement);
    advance(3000);
    fireEvent.click(document.querySelector(".booster-stage__actions button") as HTMLElement);

    // the first (a common) turns at once…
    advance(300);
    expect(states().slice(0, 2)).toEqual(["revealed", "hidden"]);
    // …and is still alone, read, after its turn and well over a second more
    advance(1800);
    expect(states()[1]).toBe("hidden");
    advance(400);
    expect(states()[1]).not.toBe("hidden");
  });

  it("skips a card turned by hand meanwhile", () => {
    const { states } = stage();
    fireEvent.click(document.querySelector(".booster-stage__tear") as HTMLElement);
    advance(3000);
    fireEvent.click(document.querySelector(".booster-stage__actions button") as HTMLElement);
    advance(300);
    // the third turned by hand while the first is read
    fireEvent.click(document.querySelectorAll<HTMLElement>(".booster-card__button")[2] as HTMLElement);
    advance(5000);
    expect(states().slice(0, 3)).toEqual(["revealed", "revealed", "revealed"]);
    expect(states()[3]).toBe("hidden");
  });
});
