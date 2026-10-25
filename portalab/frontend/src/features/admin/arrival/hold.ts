import { useSyncExternalStore } from "react";

/**
 * Issue 249 — while the arrival wizard puts the portal in place (it signs the new administrator in midway) or
 * brings an archive in, the sign-in gate keeps showing it: the session that appears must not swap the wizard
 * for the portal before it is over. Released, the gate shows the portal at ``/setup``, where the wizard goes on.
 */
let held = false;
const listeners = new Set<() => void>();

export function holdArrival(on: boolean) {
  if (held === on) return;
  held = on;
  for (const listener of listeners) listener();
}

export function useArrivalHeld(): boolean {
  return useSyncExternalStore(
    (listener) => {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
    () => held,
    () => false,
  );
}
