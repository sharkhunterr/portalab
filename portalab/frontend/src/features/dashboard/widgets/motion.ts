import { type RefObject, useEffect, useRef, useState } from "react";

/**
 * 027 (#29): an animated widget only moves when it can be seen — on screen, the tab shown, and motion not
 * reduced (the system's preference or the theme's). Timers (a wall turning posters, a deck shuffling…)
 * wait for it; CSS animations are paused by the frame (``data-offscreen``) and the root (``data-tab-hidden``).
 */
export function useLively(ref: RefObject<HTMLElement | null>): boolean {
  const [onScreen, setOnScreen] = useState(true);
  const [shown, setShown] = useState(() => typeof document === "undefined" || !document.hidden);
  useEffect(() => {
    const element = ref.current;
    if (!element || typeof IntersectionObserver === "undefined") return;
    const watch = new IntersectionObserver((entries) => setOnScreen(entries.some((e) => e.isIntersecting)));
    watch.observe(element);
    return () => watch.disconnect();
  }, [ref]);
  useEffect(() => {
    const change = () => setShown(!document.hidden);
    document.addEventListener("visibilitychange", change);
    return () => document.removeEventListener("visibilitychange", change);
  }, []);
  return onScreen && shown && !reducedMotion();
}

/** The frame marks a widget out of sight (``data-offscreen``) so its CSS animations pause. */
export function useOffscreen(ref: RefObject<HTMLElement | null>): void {
  useEffect(() => {
    const element = ref.current;
    if (!element || typeof IntersectionObserver === "undefined") return;
    const watch = new IntersectionObserver((entries) => {
      for (const entry of entries) element.toggleAttribute("data-offscreen", !entry.isIntersecting);
    });
    watch.observe(element);
    return () => watch.disconnect();
  }, [ref]);
}

// a hidden tab pauses every widget animation (``data-tab-hidden`` on the root)
if (typeof document !== "undefined") {
  document.addEventListener("visibilitychange", () =>
    document.documentElement.toggleAttribute("data-tab-hidden", document.hidden),
  );
}

export function reducedMotion(): boolean {
  if (typeof window === "undefined") return false;
  const root = document.documentElement;
  return (
    root.dataset.motion === "none" ||
    root.dataset.reducedMotion === "true" ||
    Boolean(window.matchMedia?.("(prefers-reduced-motion: reduce)").matches)
  );
}

/** Counts a figure up from 0 when it first shows, then from the last value shown to a new one (at once when
 * motion is reduced, or off screen). */
export function useCountUp(target: number, active: boolean, duration = 1200): number {
  const [value, setValue] = useState(() => (reducedMotion() ? target : 0));
  const shown = useRef(value);
  useEffect(() => {
    const from = shown.current;
    if (!active || reducedMotion() || from === target) {
      shown.current = target;
      setValue(target);
      return;
    }
    let frame = 0;
    const start = performance.now();
    const step = (now: number) => {
      const t = Math.min(1, (now - start) / duration);
      shown.current = from + (target - from) * (1 - (1 - t) ** 3); // ease out
      setValue(shown.current);
      if (t < 1) frame = requestAnimationFrame(step);
    };
    frame = requestAnimationFrame(step);
    return () => cancelAnimationFrame(frame);
  }, [target, active, duration]);
  return value;
}
