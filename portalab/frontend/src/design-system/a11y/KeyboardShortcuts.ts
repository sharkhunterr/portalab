/**
 * Keyboard shortcut registry (spec 022 T024; consumed by the shell 004 and the command palette 008).
 * Shortcuts are discoverable (``list()``), owner-tagged, never fire while the user types in a field (unless
 * declared ``global``) and never trap focus: handlers run, then focus stays where the user put it.
 */

export interface Shortcut {
  id: string;
  keys: string; // e.g. "mod+k", "g h", "?"
  description: string;
  owner: string;
  global?: boolean;
  run: () => void;
}

function isTyping(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  return target.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName);
}

export function normalize(event: KeyboardEvent): string {
  const parts: string[] = [];
  if (event.metaKey || event.ctrlKey) parts.push("mod");
  if (event.altKey) parts.push("alt");
  if (event.shiftKey && event.key.length > 1) parts.push("shift");
  parts.push(event.key.toLowerCase());
  return parts.join("+");
}

export class ShortcutRegistry {
  private shortcuts = new Map<string, Shortcut>();

  register(shortcut: Shortcut): () => void {
    const clash = [...this.shortcuts.values()].find((s) => s.keys === shortcut.keys && s.id !== shortcut.id);
    if (clash) {
      throw new Error(`shortcut ${shortcut.keys} is already used by ${clash.id}`);
    }
    this.shortcuts.set(shortcut.id, shortcut);
    return () => this.shortcuts.delete(shortcut.id);
  }

  unregister(owner: string): number {
    let removed = 0;
    for (const [id, shortcut] of this.shortcuts) {
      if (shortcut.owner === owner) {
        this.shortcuts.delete(id);
        removed += 1;
      }
    }
    return removed;
  }

  list(): Shortcut[] {
    return [...this.shortcuts.values()].sort((a, b) => a.keys.localeCompare(b.keys));
  }

  handle(event: KeyboardEvent): boolean {
    const keys = normalize(event);
    const shortcut = [...this.shortcuts.values()].find((s) => s.keys === keys);
    if (!shortcut || (isTyping(event.target) && !shortcut.global)) return false;
    event.preventDefault();
    shortcut.run();
    return true;
  }

  attach(target: Document | HTMLElement = document): () => void {
    const listener = (event: Event) => this.handle(event as KeyboardEvent);
    target.addEventListener("keydown", listener);
    return () => target.removeEventListener("keydown", listener);
  }
}

export const shortcuts = new ShortcutRegistry();
