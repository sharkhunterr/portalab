import type { UiPolicy } from "./preferences";

/** Effective text scale: the user's choice clamped to the policy bounds (the stored choice is kept). */
export function effectiveTextScale(scale: number, policy: UiPolicy): number {
  return Math.min(policy.textScaleMax, Math.max(policy.textScaleMin, scale));
}
