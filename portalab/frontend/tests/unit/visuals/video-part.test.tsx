import { act, cleanup, render } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { normaliseElement } from "../../../src/design-system/visuals/registry";
import { ScenePart } from "../../../src/features/marketplace/boosters/scene/scene";

// Issue 287: a scene's part may be a video — a reveal's plays behind the card and its second one over it; read
// once (its local address), nothing at all when motion is reduced, nothing left once it has played.
const reveal = normaliseElement({
  pack: "p",
  sha: "0123456789abcdef",
  type: "card_reveal",
  look: "p-rare",
  kind: "video",
  file: "/api/v1/visuals/files/p/0123456789abcdef/reveal-rare/reveal.mp4",
  over: "/api/v1/visuals/files/p/0123456789abcdef/reveal-rare/over.mp4",
  alpha: "none",
});
const context = { reducedMotion: false, phase: "reveal", rarity: "rare", index: 0, count: 1 };

describe("a video part", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({ ok: true, blob: async () => new Blob(["video"], { type: "video/mp4" }) })),
    );
    URL.createObjectURL = vi.fn((blob: Blob) => `blob:${blob.size}`);
    HTMLMediaElement.prototype.play = vi.fn(async () => {});
    HTMLMediaElement.prototype.pause = vi.fn();
  });
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it("plays behind the card and over it, from its local copy", async () => {
    const { container } = render(
      <ScenePart element={reveal} className="booster-fx__scene" context={context} />,
    );
    await act(async () => {});
    const layers = container.querySelectorAll(".booster-fx__scene");
    expect(layers).toHaveLength(2);
    expect(layers[0]?.hasAttribute("data-over")).toBe(false);
    expect(layers[1]?.getAttribute("data-over")).toBe("true");
    const videos = container.querySelectorAll("video");
    expect([...videos].every((v) => v.muted && v.src.startsWith("blob:") && !v.loop)).toBe(true);
    expect(HTMLMediaElement.prototype.play).toHaveBeenCalled();
    // played once, it leaves nothing behind
    await act(async () => {
      videos[0]?.dispatchEvent(new Event("ended"));
    });
    expect(container.querySelectorAll(".booster-fx__scene")).toHaveLength(1);
  });

  it("draws nothing when motion is reduced", () => {
    const { container } = render(
      <ScenePart
        element={reveal}
        className="booster-fx__scene"
        context={{ ...context, reducedMotion: true }}
      />,
    );
    expect(container.innerHTML).toBe("");
  });
});
