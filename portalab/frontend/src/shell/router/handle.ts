import type { Params } from "react-router";

/** Route metadata (spec 004 T022): breadcrumb label (static or from params), contextual links key, whether
 * the route reveals an object's existence, and the permission the UI expects (a hint — the API decides). */
export interface RouteHandle {
  crumb?: string | ((params: Params) => string);
  existenceSensitive?: boolean;
  requiredPermission?: string;
}

export function crumbOf(handle: unknown, params: Params): string | null {
  const crumb = (handle as RouteHandle | undefined)?.crumb;
  if (!crumb) return null;
  return typeof crumb === "function" ? crumb(params) : crumb;
}
