import { useSyncExternalStore } from "react";

/**
 * The bars drawn over the bottom of the screen — a player's bar (the radio, an audiobook…) — and how far up
 * from the bottom the highest one reaches, so that what floats in a corner (the assistant's button) moves
 * above them instead of hiding under them. A bar takes part by its ref: ``<section ref={bottomOverlay}>``.
 */

const reach = new Map<Element, number>();
const listeners = new Set<() => void>();
let highest = 0;

function update() {
  const next = Math.round(Math.max(0, ...reach.values()));
  if (next === highest) return;
  highest = next;
  for (const listener of listeners) listener();
}

/** A bar's ref: measured while it is there (its size, the window's), forgotten once it is gone. */
export function bottomOverlay(element: HTMLElement | null): (() => void) | undefined {
  if (!element) return undefined;
  const measure = () => {
    const box = element.getBoundingClientRect();
    reach.set(element, box.height ? window.innerHeight - box.top : 0);
    update();
  };
  const sizes = typeof ResizeObserver === "undefined" ? null : new ResizeObserver(measure);
  sizes?.observe(element);
  window.addEventListener("resize", measure);
  measure();
  return () => {
    sizes?.disconnect();
    window.removeEventListener("resize", measure);
    reach.delete(element);
    update();
  };
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

/** How many pixels from the bottom of the screen the bars cover (0: none). */
export function useBottomOverlays(): number {
  return useSyncExternalStore(
    subscribe,
    () => highest,
    () => 0,
  );
}
