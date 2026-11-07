import { createContext, type RefObject, useContext, useEffect } from "react";
import { STILL_ATTRIBUTE } from "./budget";

/**
 * Issue 381: motion held still in one part of a page only (a shop's previews while browsing; the same
 * preview opened on its own still moves) — the canvas renderers read the zone's attribute, the JavaScript
 * replays this context, and the CSS animations and transitions inside it are held by ``useHeldMotion``.
 */
const StillMotion = createContext(false);

export const StillMotionZone = StillMotion.Provider;

/** Whether the motion around is held still. */
export function useStillMotion(): boolean {
  return useContext(StillMotion);
}

function hold(target: Element) {
  for (const animation of target.getAnimations({ subtree: true })) {
    const end = animation.effect?.getComputedTiming().endTime;
    // an entrance ends as it would (its last frame); a loop stops where it is
    if (typeof end === "number" && Number.isFinite(end)) animation.finish();
    else animation.pause();
  }
}

/** Holds the CSS animations and transitions inside ``ref`` (and those that start later) while ``held``;
 * marks it a still zone for the canvas renderers. */
export function useHeldMotion(ref: RefObject<HTMLElement | null>, held: boolean): void {
  useEffect(() => {
    const root = ref.current;
    if (!root || !held) return;
    root.setAttribute(STILL_ATTRIBUTE, "");
    if (typeof root.getAnimations !== "function") return () => root.removeAttribute(STILL_ATTRIBUTE);
    hold(root);
    const started = (event: Event) => {
      if (event.target instanceof Element) hold(event.target);
    };
    root.addEventListener("animationstart", started, true);
    root.addEventListener("transitionrun", started, true);
    return () => {
      root.removeAttribute(STILL_ATTRIBUTE);
      root.removeEventListener("animationstart", started, true);
      root.removeEventListener("transitionrun", started, true);
      for (const animation of root.getAnimations({ subtree: true })) {
        if (animation.playState === "paused") animation.play();
      }
    };
  }, [ref, held]);
}
