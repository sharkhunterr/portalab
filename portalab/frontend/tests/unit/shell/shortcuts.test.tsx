import { act, fireEvent, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ShortcutManager } from "../../../src/shell/shortcuts/ShortcutManager";

// 004 T026 — baseline catalog (Mod+K, /, g-chords, ?, Esc via Radix); inactive in inputs; user
// customization; conflict detection.

const fake = vi.hoisted(() => ({
  handler: (_: Request): Response | Promise<Response> => new Response(null),
}));
vi.mock("../../../src/api/client", async (importOriginal) => {
  const { installFakeApi } = await import("../../support/fake-api");
  const installed = installFakeApi();
  Object.defineProperty(installed, "handler", { get: () => fake.handler });
  return importOriginal();
});

import { json } from "../../support/fake-api";
import { renderShell, VIEW } from "./harness";

function key(init: KeyboardEventInit, target: EventTarget = document.body) {
  const event = new KeyboardEvent("keydown", { bubbles: true, cancelable: true, ...init });
  target.dispatchEvent(event);
  return event;
}

describe("shortcut manager", () => {
  it("chords, typing guard, overrides and conflicts", () => {
    const go = vi.fn();
    const palette = vi.fn();
    const manager = new ShortcutManager(
      [
        { id: "palette", description: "palette", defaultKeys: "mod+k", run: palette },
        { id: "go-home", description: "home", defaultKeys: "g h", run: go },
      ],
      { "go-home": "g o" },
    );
    const input = document.createElement("input");
    document.body.append(input);
    manager.handle(key({ key: "g" }, input));
    expect(manager.handle(key({ key: "o" }))).toBe(false); // the chord did not start while typing
    manager.handle(key({ key: "g" }));
    manager.handle(key({ key: "o" }));
    expect(go).toHaveBeenCalledTimes(1);
    manager.handle(key({ key: "k", ctrlKey: true }, input)); // Mod+K works even in a field
    expect(palette).toHaveBeenCalledTimes(1);
    expect(manager.list().map((s) => s.keys)).toEqual(["g o", "mod+k"]);
    expect(
      () =>
        new ShortcutManager([
          { id: "a", description: "a", defaultKeys: "?", run: () => undefined },
          { id: "b", description: "b", defaultKeys: "?", run: () => undefined },
        ]),
    ).toThrow(/used by both a and b/);
    input.remove();
  });

  it("in the shell: Mod+K opens the palette, ? shows the help, g s goes to services", async () => {
    fake.handler = () => json(200, VIEW);
    const { router } = renderShell();
    await screen.findByRole("link", { name: "Services" });
    act(() => {
      key({ key: "k", ctrlKey: true });
    });
    expect(await screen.findByRole("combobox")).toBeInTheDocument();
    fireEvent.keyDown(screen.getByRole("combobox"), { key: "Escape" });
    act(() => {
      key({ key: "?" });
    });
    expect(await screen.findByRole("dialog", { name: "Keyboard shortcuts" })).toBeInTheDocument();
    fireEvent.keyDown(screen.getByRole("dialog"), { key: "Escape" });
    act(() => {
      key({ key: "g" });
      key({ key: "s" });
    });
    expect(router.state.location.pathname).toBe("/services");
  });
});
