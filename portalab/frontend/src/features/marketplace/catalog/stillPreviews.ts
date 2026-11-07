import { useSyncExternalStore } from "react";

/**
 * Issue 381: the shop's previews held still while browsing — the member's choice, kept on this device (a
 * product opened on its own still moves).
 */
const KEY = "portalab.marketplace.stillPreviews";
const listeners = new Set<() => void>();

function read(): boolean {
  try {
    return window.localStorage.getItem(KEY) === "1";
  } catch {
    return false;
  }
}

let still = typeof window === "undefined" ? false : read();

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function setStillPreviews(value: boolean): void {
  still = value;
  try {
    if (value) window.localStorage.setItem(KEY, "1");
    else window.localStorage.removeItem(KEY);
  } catch {
    // the choice lasts this visit only
  }
  for (const listener of listeners) listener();
}

export function useStillPreviews(): boolean {
  return useSyncExternalStore(
    subscribe,
    () => still,
    () => false,
  );
}
