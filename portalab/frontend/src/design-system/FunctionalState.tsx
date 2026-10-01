import type { ReactNode } from "react";

/**
 * Standardized functional states (CD-022, constitution XI). Themes change their appearance through
 * design tokens only; the meaning, the icon and the text label never change, so a state is never conveyed
 * by color alone (FR-004, CD-027 / WCAG 2.2 AA).
 */
export const FUNCTIONAL_STATES = [
  "loading",
  "available",
  "partial",
  "stale",
  "error",
  "unavailable",
  "maintenance",
  "unauthorized",
  "no-data",
  "syncing",
] as const;

export type FunctionalStateName = (typeof FUNCTIONAL_STATES)[number];

/** Default English labels — replaced by i18n catalogs (spec 026). */
export const STATE_LABELS: Record<FunctionalStateName, string> = {
  loading: "Loading",
  available: "Available",
  partial: "Partially available",
  stale: "Out of date",
  error: "Error",
  unavailable: "Unavailable",
  maintenance: "Under maintenance",
  unauthorized: "Not allowed",
  "no-data": "No data yet",
  syncing: "Syncing",
};

const ICON_PATHS: Record<FunctionalStateName, string> = {
  loading: "M12 3a9 9 0 1 0 9 9h-2a7 7 0 1 1-7-7z",
  available: "M9 16.2 4.8 12l-1.4 1.4L9 19 21 7l-1.4-1.4z",
  partial: "M12 2a10 10 0 1 0 0 20V2z",
  stale: "M12 7v5l4 2M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18z",
  error: "M12 2 1 21h22zm0 6v6m0 3v.01",
  unavailable: "M4 4l16 16M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18z",
  maintenance: "M14.7 6.3a4 4 0 0 0-5.4 5.4L3 18l3 3 6.3-6.3a4 4 0 0 0 5.4-5.4l-2.5 2.5-2.1-2.1z",
  unauthorized: "M7 11V8a5 5 0 0 1 10 0v3M5 11h14v10H5z",
  "no-data": "M4 6h16M4 12h16M4 18h10",
  syncing: "M4 12a8 8 0 0 1 14-5.3L20 9M20 12a8 8 0 0 1-14 5.3L4 15",
};

const ASSERTIVE: ReadonlySet<FunctionalStateName> = new Set(["error", "unauthorized"]);

export interface FunctionalStateProps {
  state: FunctionalStateName;
  /** Overrides the default label (already localized by the caller). */
  label?: string;
  detail?: ReactNode;
  /** Freshness of the data (rendered for stale/partial data). */
  asOf?: Date;
  onRetry?: () => void;
  retryLabel?: string;
}

export function FunctionalState({
  state,
  label,
  detail,
  asOf,
  onRetry,
  retryLabel = "Retry",
}: FunctionalStateProps) {
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
        viewBox="0 0 24 24"
        width="20"
        height="20"
        aria-hidden="true"
        focusable="false"
      >
        <path d={ICON_PATHS[state]} fill="none" stroke="currentColor" strokeWidth="2" />
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
