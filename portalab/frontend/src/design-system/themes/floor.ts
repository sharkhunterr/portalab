import { contrast, LARGE_OR_UI_MIN, TEXT_MIN } from "./contrast";
import { CRITICAL_STATES, FUNCTIONAL_STATES, type ThemeDefinition } from "./schema";

/**
 * Accessibility floor (spec 022 R4, FR-013/014, CD-027): every theme must pass WCAG 2.2 AA on its
 * declared pairs, keep critical states visible (never hidden, never faint, distinct from the surface) and
 * give imagery a solid fallback. The backend runs the same rules at registration.
 */
export const CRITICAL_MIN_OPACITY = 0.9;

export interface FloorCheck {
  pair: string;
  ratio: number;
  minimum: number;
  ok: boolean;
}

export interface FloorReport {
  ok: boolean;
  checks: FloorCheck[];
  violations: string[];
}

export function floorReport(theme: ThemeDefinition): FloorReport {
  const { colors } = theme;
  const surface = theme.background?.fallback ?? colors.surface;
  const checks: FloorCheck[] = [];
  const check = (pair: string, fg: string, bg: string, minimum = TEXT_MIN, base = surface) => {
    const ratio = Math.round(contrast(fg, bg, base) * 100) / 100;
    checks.push({ pair, ratio, minimum, ok: ratio >= minimum });
  };
  check("text/surface", colors.text, colors.surface);
  check("text/surfaceRaised", colors.text, colors.surfaceRaised);
  check("textMuted/surface", colors.textMuted, colors.surface);
  check("accentContrast/accent", colors.accentContrast, colors.accent);
  check("focus/surface", colors.focus, colors.surface, LARGE_OR_UI_MIN);
  if (theme.background) {
    check("text/backgroundFallback", colors.text, theme.background.fallback);
  }
  for (const state of FUNCTIONAL_STATES) {
    const style = theme.states[state];
    check(`state.${state}.fg/bg`, style.fg, style.bg, TEXT_MIN);
    if (CRITICAL_STATES.includes(state)) {
      check(`state.${state}.fg/surface`, style.fg, colors.surface, LARGE_OR_UI_MIN);
    }
  }
  const violations = checks
    .filter((c) => !c.ok)
    .map((c) => `${c.pair} is ${c.ratio}:1, needs ${c.minimum}:1`);
  for (const state of CRITICAL_STATES) {
    const style = theme.states[state];
    if (style.display === "none") {
      violations.push(`state.${state} must never be hidden`);
    }
    if (style.opacity !== undefined && style.opacity < CRITICAL_MIN_OPACITY) {
      violations.push(`state.${state} opacity ${style.opacity} is below ${CRITICAL_MIN_OPACITY}`);
    }
  }
  return { ok: violations.length === 0, checks, violations };
}
