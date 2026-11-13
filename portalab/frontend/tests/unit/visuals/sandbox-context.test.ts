import { afterEach, describe, expect, it, vi } from "vitest";
import { normaliseElement } from "../../../src/design-system/visuals/registry";
import { runSandbox } from "../../../src/design-system/visuals/sandbox";

// 028 (US6): a pack's script starts with what it knows *now* — what changed while its frame was loading
// (a widget's data arriving) is never lost to the context it was created with.

afterEach(() => {
  vi.unstubAllGlobals();
  document.body.innerHTML = "";
});

describe("sandbox context", () => {
  it("runs with the latest context, then posts the next ones", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response("export default () => {}", { status: 200 })),
    );
    const frame = document.createElement("iframe");
    document.body.append(frame);
    const element = normaliseElement({
      pack: "vigie",
      type: "widget",
      look: "cap",
      file: "/x/sha-a/w/cap.js",
    });
    const sandbox = runSandbox(frame, element, { data: { "me.statistics": { state: "loading" } } });
    const target = frame.contentWindow as Window;
    const posted: Array<Record<string, unknown>> = [];
    target.postMessage = ((message: Record<string, unknown>) =>
      posted.push(message)) as Window["postMessage"];
    sandbox.update({ data: { "me.statistics": { streak_days: 4 } } }); // before the frame has loaded
    window.dispatchEvent(new MessageEvent("message", { source: target, data: { type: "loaded" } }));
    await vi.waitFor(() => expect(posted.some((m) => m.type === "run")).toBe(true));
    const run = posted.find((m) => m.type === "run") as { context: { data: Record<string, unknown> } };
    expect(run.context.data["me.statistics"]).toEqual({ streak_days: 4 });
    sandbox.update({ data: { "me.statistics": { streak_days: 5 } } });
    expect(posted.at(-1)).toEqual({
      type: "context",
      context: { data: { "me.statistics": { streak_days: 5 } } },
    });
    sandbox.stop();
  });
});

describe("a script that leaves its sandbox page", () => {
  it("hears nothing more: its frame emptied, the failure reported (issue 396)", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response("export default () => {}", { status: 200 })),
    );
    const frame = document.createElement("iframe");
    document.body.append(frame);
    const element = normaliseElement({
      pack: "vigie",
      type: "widget",
      look: "cap",
      file: "/x/sha-a/w/cap.js",
    });
    const onError = vi.fn();
    const sandbox = runSandbox(frame, element, { data: {} }, { onError });
    const target = frame.contentWindow as Window;
    const posted: Array<Record<string, unknown>> = [];
    target.postMessage = ((message: Record<string, unknown>) =>
      posted.push(message)) as Window["postMessage"];
    frame.dispatchEvent(new Event("load")); // the sandbox page
    window.dispatchEvent(new MessageEvent("message", { source: target, data: { type: "loaded" } }));
    await vi.waitFor(() => expect(posted.some((m) => m.type === "run")).toBe(true));
    frame.dispatchEvent(new Event("load")); // the script sent its frame elsewhere
    const before = posted.length;
    sandbox.update({ data: { "me.statistics": { secret: 1 } } });
    expect(posted.length).toBe(before);
    expect(onError).toHaveBeenCalledWith("the script left its sandbox page");
    expect(frame.hasAttribute("src")).toBe(false);
    sandbox.stop();
  });
});
