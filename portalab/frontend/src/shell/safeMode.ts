/**
 * 029: safe mode — Portalab's interface without anything brought by a pack (no look, palette, scene,
 * navigation or interface of a pack), until the member leaves it: a way out when a pack breaks the display.
 * Entered from the appearance settings or from any address with ``?safe=1`` (bookmarkable), left with
 * ``?safe=0`` or its banner. Kept in this browser only (it never needs the server); the page reloads on
 * entering and leaving, so nothing of a pack stays loaded.
 */
const KEY = "portalab.safe";
const listeners = new Set<() => void>();

function stores(): Storage[] {
  const out: Storage[] = [];
  try {
    out.push(window.localStorage);
  } catch {
    // refused
  }
  try {
    out.push(window.sessionStorage);
  } catch {
    // refused
  }
  return out;
}

let fallback = false; // when no storage answers

export function isSafeMode(): boolean {
  if (typeof window === "undefined") return false;
  for (const store of stores()) {
    try {
      if (store.getItem(KEY) === "1") return true;
    } catch {
      // ignored
    }
  }
  return fallback;
}

export function setSafeMode(on: boolean): void {
  fallback = on;
  for (const store of stores()) {
    try {
      if (on) store.setItem(KEY, "1");
      else store.removeItem(KEY);
    } catch {
      // ignored
    }
  }
  for (const listener of listeners) listener();
}

/** ``?safe=1`` / ``?safe=0`` on the address: applied once at start, then removed from the address. */
export function applySafeModeFromAddress(): void {
  if (typeof window === "undefined") return;
  const url = new URL(window.location.href);
  const asked = url.searchParams.get("safe");
  if (asked !== "1" && asked !== "0") return;
  setSafeMode(asked === "1");
  url.searchParams.delete("safe");
  window.history.replaceState(window.history.state, "", url.pathname + url.search + url.hash);
}

/** Enters or leaves safe mode, the page reloaded (nothing of a pack stays loaded, everything comes back). */
export function switchSafeMode(on: boolean): void {
  setSafeMode(on);
  window.location.reload();
}
