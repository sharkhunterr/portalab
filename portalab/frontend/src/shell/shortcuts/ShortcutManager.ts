/**
 * Keyboard shortcuts (spec 004 T028; R10, OQ-16 default): ``Mod+K`` palette, ``/`` search, ``g`` then a
 * letter to go somewhere, ``?`` help, ``Escape`` closes overlays (Radix). Shortcuts never fire while typing
 * in a field, users may remap them (``shell.shortcuts`` preference), and a conflicting mapping is refused.
 */
export interface ShortcutAction {
  id: string;
  description: string;
  defaultKeys: string;
  run: () => void;
}

export function isTyping(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  return target.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName);
}

export function keyOf(event: KeyboardEvent): string {
  const mod = event.metaKey || event.ctrlKey ? "mod+" : "";
  // 027: Shift counts with a modifier and a letter (Mod+Shift+K); « ? » stays « ? »
  const shift = mod && event.shiftKey && /^[a-z]$/i.test(event.key) ? "shift+" : "";
  return `${mod}${shift}${event.key.toLowerCase()}`;
}

export class ShortcutManager {
  private bindings = new Map<string, ShortcutAction>();
  private pendingChord: string | null = null;
  private chordTimer: ReturnType<typeof setTimeout> | null = null;

  constructor(actions: ShortcutAction[], overrides: Record<string, string> = {}) {
    for (const action of actions) {
      const keys = (overrides[action.id] ?? action.defaultKeys).toLowerCase();
      const clash = this.bindings.get(keys);
      if (clash) {
        throw new Error(`shortcut "${keys}" is used by both ${clash.id} and ${action.id}`);
      }
      this.bindings.set(keys, action);
    }
  }

  list(): Array<{ keys: string; action: ShortcutAction }> {
    return [...this.bindings.entries()]
      .map(([keys, action]) => ({ keys, action }))
      .sort((a, b) => a.keys.localeCompare(b.keys));
  }

  handle(event: KeyboardEvent): boolean {
    const key = keyOf(event);
    const typing = isTyping(event.target);
    if (typing && key !== "mod+k" && key !== "mod+shift+k") return false;
    if (this.pendingChord) {
      const chord = `${this.pendingChord} ${key}`;
      this.clearChord();
      const action = this.bindings.get(chord);
      if (action) {
        event.preventDefault();
        action.run();
        return true;
      }
      return false;
    }
    const action = this.bindings.get(key);
    if (action) {
      event.preventDefault();
      action.run();
      return true;
    }
    if ([...this.bindings.keys()].some((keys) => keys.startsWith(`${key} `))) {
      this.pendingChord = key;
      this.chordTimer = setTimeout(() => this.clearChord(), 1500);
      return true;
    }
    return false;
  }

  private clearChord(): void {
    this.pendingChord = null;
    if (this.chordTimer) clearTimeout(this.chordTimer);
    this.chordTimer = null;
  }

  attach(target: Document = document): () => void {
    const listener = (event: Event) => this.handle(event as KeyboardEvent);
    target.addEventListener("keydown", listener);
    return () => target.removeEventListener("keydown", listener);
  }
}
