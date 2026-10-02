import type { ReactNode } from "react";
import { useTheme } from "../themes/ThemeProvider";
import {
  DEFAULT_ICONS,
  type FunctionalStateName,
  ICON_PATHS,
  isFunctionalState,
  STATE_LABELS,
} from "./stateMap";

/**
 * ``FunctionalState`` (spec 022 T012, retrofitting the 001 seed): icon + text + color, never color alone.
 * The active theme's ``states`` map may change the icon and colors; the accessible name, ``data-state``
 * and meaning stay identical across themes. Unknown states are rejected.
 */
export { FUNCTIONAL_STATES, type FunctionalStateName, STATE_LABELS } from "./stateMap";

const ASSERTIVE: ReadonlySet<FunctionalStateName> = new Set(["error", "unauthorized"]);

export interface FunctionalStateProps {
  state: FunctionalStateName;
  /** Overrides the default label (already localized by the caller). */
  label?: string | undefined;
  detail?: ReactNode;
  /** Freshness of the data (rendered for stale/partial data). */
  asOf?: Date | undefined;
  onRetry?: (() => void) | undefined;
  retryLabel?: string | undefined;
}

export function FunctionalState({
  state,
  label,
  detail,
  asOf,
  onRetry,
  retryLabel = "Retry",
}: FunctionalStateProps) {
  if (!isFunctionalState(state)) {
    throw new Error(`unknown functional state: ${String(state)}`);
  }
  const { stateStyle } = useTheme();
  const icon = stateStyle(state)?.icon ?? DEFAULT_ICONS[state];
  const text = label ?? STATE_LABELS[state];
  return (
    <div
      className={`functional-state functional-state--${state}`}
      data-state={state}
      role={ASSERTIVE.has(state) ? "alert" : "status"}
      aria-live={ASSERTIVE.has(state) ? "assertive" : "polite"}
      aria-busy={state === "loading" || state === "syncing" ? true : undefined}
    >
      <svg
        className="functional-state__icon"
        data-icon={icon}
        viewBox="0 0 24 24"
        width="20"
        height="20"
        aria-hidden="true"
        focusable="false"
      >
        <path d={ICON_PATHS[icon]} fill="none" stroke="currentColor" strokeWidth="2" />
      </svg>
      <span className="functional-state__label">{text}</span>
      {detail ? <span className="functional-state__detail">{detail}</span> : null}
      {asOf ? (
        <time className="functional-state__as-of" dateTime={asOf.toISOString()}>
          {asOf.toISOString()}
        </time>
      ) : null}
      {onRetry ? (
        <button type="button" className="functional-state__retry" onClick={onRetry}>
          {retryLabel}
        </button>
      ) : null}
    </div>
  );
}
