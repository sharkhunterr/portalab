import { type QueryKey, useQuery } from "@tanstack/react-query";
import { Component, type ErrorInfo, type ReactNode } from "react";
import { FunctionalState, type FunctionalStateName } from "../design-system/FunctionalState";

/**
 * Independent data region (plan §4, spec 001 US4, principle IX): each region owns its query, its loading
 * and error states and an error boundary, so a slow or failing region never blocks or breaks its siblings.
 */

export class ApiError extends Error {
  readonly status: number;
  readonly code: string | undefined;
  /** Extra members of the problem document (e.g. `retry_after_seconds`), never secrets. */
  readonly extensions: Readonly<Record<string, unknown>>;

  constructor(status: number, message: string, code?: string, extensions: Record<string, unknown> = {}) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.extensions = extensions;
  }
}

export function stateForError(error: unknown): FunctionalStateName {
  if (error instanceof ApiError) {
    if (error.status === 401 || error.status === 403) return "unauthorized";
    if (error.status === 503 && error.code?.startsWith("maintenance")) return "maintenance";
    if (error.status === 503 || error.status === 504) return "unavailable";
  }
  return "error";
}

interface BoundaryProps {
  label: string;
  children: ReactNode;
}

interface BoundaryState {
  failed: boolean;
}

class RegionBoundary extends Component<BoundaryProps, BoundaryState> {
  override state: BoundaryState = { failed: false };

  static getDerivedStateFromError(): BoundaryState {
    return { failed: true };
  }

  override componentDidCatch(error: Error, info: ErrorInfo): void {
    // Reported to Observability (spec 025) once the client error hook exists; never rethrown.
    void error;
    void info;
  }

  override render(): ReactNode {
    if (this.state.failed) {
      return (
        <FunctionalState
          state="error"
          detail={this.props.label}
          onRetry={() => this.setState({ failed: false })}
        />
      );
    }
    return this.props.children;
  }
}

export interface DataRegionProps<T> {
  /** Accessible name of the region. */
  label: string;
  queryKey: QueryKey;
  queryFn: () => Promise<T>;
  isEmpty?: (data: T) => boolean;
  children: (data: T) => ReactNode;
  /** Refresh every N ms while it returns a number (027: live progress of running tasks). */
  poll?: ((data: T | undefined) => number | false) | undefined;
}

function RegionContent<T>({ label, queryKey, queryFn, isEmpty, children, poll }: DataRegionProps<T>) {
  const query = useQuery({
    queryKey,
    queryFn,
    ...(poll ? { refetchInterval: (q: { state: { data: T | undefined } }) => poll(q.state.data) } : {}),
  });
  if (query.isPending) return <FunctionalState state="loading" detail={label} />;
  if (query.isError) {
    return (
      <FunctionalState
        state={stateForError(query.error)}
        detail={label}
        onRetry={() => void query.refetch()}
      />
    );
  }
  if (isEmpty?.(query.data)) return <FunctionalState state="no-data" detail={label} />;
  return <>{children(query.data)}</>;
}

export function DataRegion<T>(props: DataRegionProps<T>) {
  return (
    <section aria-label={props.label} className="data-region">
      <RegionBoundary label={props.label}>
        <RegionContent {...props} />
      </RegionBoundary>
    </section>
  );
}
