import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { ExternalElement } from "../../../src/design-system/visuals/registry";
import { runSandbox } from "../../../src/design-system/visuals/sandbox";

// 029 — a script's navigations are paced (one per 400 ms), but the last key asked during the pause is
// opened once it is over, never dropped; nothing is opened after the sandbox stopped.

const element = {
  type: "navigation",
  look: "demo",
  pack: "demo",
  sha: "abc",
  product: "p",
} as unknown as ExternalElement;

let frame: HTMLIFrameElement;
beforeEach(() => {
  vi.useFakeTimers();
  frame = document.createElement("iframe");
  document.body.append(frame);
});
afterEach(() => {
  vi.useRealTimers();
  frame.remove();
});

const ask = (key: string) =>
  window.dispatchEvent(
    new MessageEvent("message", { data: { type: "navigate", key }, source: frame.contentWindow }),
  );

describe("sandbox navigation", () => {
  it("opens the first at once and the last asked during the pause after it", () => {
    const opened: string[] = [];
    const sandbox = runSandbox(frame, element, {}, { onNavigate: (key) => opened.push(key) });
    ask("media");
    ask("wiki");
    ask("community");
    expect(opened).toEqual(["media"]);
    vi.advanceTimersByTime(400);
    expect(opened).toEqual(["media", "community"]);
    sandbox.stop();
  });

  it("opens nothing once stopped", () => {
    const opened: string[] = [];
    const sandbox = runSandbox(frame, element, {}, { onNavigate: (key) => opened.push(key) });
    ask("media");
    ask("wiki");
    sandbox.stop();
    vi.advanceTimersByTime(1000);
    expect(opened).toEqual(["media"]);
  });
});
