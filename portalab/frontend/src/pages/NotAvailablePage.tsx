import { RouteStateView } from "../shell/router/RouteBoundary";

export default function NotAvailablePage() {
  return <RouteStateView inline state="not-found" />; // issue 448: no route at this address
}
