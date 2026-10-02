import type { ReducedMotion, UiPolicy } from "./preferences";

/** Reduced motion: an admin policy forcing it wins; otherwise the explicit preference, else the OS setting. */
export function reducedMotionActive(
  preference: ReducedMotion,
  policy: UiPolicy,
  systemPrefersReduced: boolean,
): boolean {
  if (policy.forceReducedMotion) return true;
  if (preference === "on") return true;
  if (preference === "off") return false;
  return systemPrefersReduced;
}

export function systemPrefersReducedMotion(): boolean {
  return typeof window !== "undefined" && typeof window.matchMedia === "function"
    ? window.matchMedia("(prefers-reduced-motion: reduce)").matches
    : false;
}
