import { Component, type ErrorInfo, type ReactNode, Suspense } from "react";
import { isRouteErrorResponse, Link, useMatches, useRouteError } from "react-router";
import { FunctionalState } from "../../design-system/state/FunctionalState";
import { ApiError } from "../../state/regions";
import { useShellStrings } from "../strings";
import type { RouteHandle } from "./handle";

/**
 * Route-level states (spec 004 T022; R12/R13, FR-026..028): loading, error, unavailable, unauthorized and
 * "not available". Existence-sensitive routes render the *same* output for a missing and a forbidden
 * object, so the page never reveals that something exists. A failing chunk or region is isolated with a
 * retry; the shell (navigation, search, palette) stays usable.
 */
export type RouteState = "unauthorized" | "not-available" | "unavailable" | "error";

export function stateFor(error: unknown, existenceSensitive: boolean): RouteState {
  const status =
    error instanceof ApiError ? error.status : isRouteErrorResponse(error) ? error.status : undefined;
  if (status === 404 || (existenceSensitive && (status === 403 || status === 404))) return "not-available";
  if (status === 401 || status === 403) return "unauthorized";
  if (status === 503 || status === 504) return "unavailable";
  return "error";
}

export function RouteStateView({ state, onRetry }: { state: RouteState; onRetry?: () => void }) {
  const shellStrings = useShellStrings();
  if (state === "not-available") {
    return (
      <div>
        <FunctionalState
          state="unavailable"
          label={shellStrings.notAvailable}
          detail={shellStrings.notAvailableDetail}
        />
        <Link to="/">{shellStrings.goHome}</Link>
      </div>
    );
  }
  if (state === "unauthorized")
    return <FunctionalState state="unauthorized" label={shellStrings.unauthorized} />;
  if (state === "unavailable")
    return <FunctionalState state="unavailable" onRetry={onRetry} retryLabel={shellStrings.retry} />;
  return (
    <FunctionalState
      state="error"
      label={shellStrings.routeError}
      onRetry={onRetry}
      retryLabel={shellStrings.retry}
    />
  );
}

/** ``errorElement`` of every route. */
export function RouteErrorElement() {
  const error = useRouteError();
  const matches = useMatches();
  const sensitive = matches.some((m) => (m.handle as RouteHandle | undefined)?.existenceSensitive);
  return <RouteStateView state={stateFor(error, sensitive)} onRetry={() => window.location.reload()} />;
}

interface BoundaryState {
  error: unknown;
}

/** Region boundary + suspense for lazy pages: a failure stays inside the page area. */
export class RegionBoundary extends Component<
  { children: ReactNode; existenceSensitive?: boolean },
  BoundaryState
> {
  override state: BoundaryState = { error: null };

  static getDerivedStateFromError(error: unknown): BoundaryState {
    return { error };
  }

  override componentDidCatch(_error: Error, _info: ErrorInfo): void {
    // reported through the observability hooks of the API calls; never rethrown
  }

  override render(): ReactNode {
    if (this.state.error) {
      return (
        <RouteStateView
          state={stateFor(this.state.error, this.props.existenceSensitive ?? false)}
          onRetry={() => this.setState({ error: null })}
        />
      );
    }
    return <Suspense fallback={<FunctionalState state="loading" />}>{this.props.children}</Suspense>;
  }
}
