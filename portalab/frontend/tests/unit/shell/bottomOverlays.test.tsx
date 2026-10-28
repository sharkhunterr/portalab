import { act, cleanup, render, screen } from "@testing-library/react";
import { useState } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { bottomOverlay, useBottomOverlays } from "../../../src/shell/bottomOverlays";

// A player's bar over the bottom of the screen (the radio, an audiobook): what floats in a corner (the
// assistant's button) is told how far up it reaches, and goes back down once the bar is closed.

function Corner() {
  return <output aria-label="covered">{useBottomOverlays()}</output>;
}

function Page() {
  const [open, setOpen] = useState(true);
  return (
    <>
      <Corner />
      {open ? (
        <section ref={bottomOverlay} aria-label="player">
          <button type="button" onClick={() => setOpen(false)}>
            close
          </button>
        </section>
      ) : null}
    </>
  );
}

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("the bars over the bottom of the screen", () => {
  it("say how far up they reach, and nothing once closed", () => {
    vi.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockReturnValue({
      top: window.innerHeight - 72,
      height: 64,
    } as DOMRect);
    render(<Page />);
    expect(screen.getByLabelText("covered").textContent).toBe("72");
    act(() => screen.getByRole("button", { name: "close" }).click());
    expect(screen.getByLabelText("covered").textContent).toBe("0");
  });
});
