import { useQuery } from "@tanstack/react-query";
import { api } from "../../api/client";
import { FunctionalState } from "../../design-system/state/FunctionalState";
import { useNavigationView } from "../nav/NavigationProvider";
import { useShellStrings } from "../strings";

/**
 * Degraded-mode banner (spec 004 T023; R12): when several services are degraded or unavailable (health
 * summary from 006), the shell says so once; navigation, search and the palette stay usable. Shown only to
 * users who may read service health; a failing summary never breaks the shell.
 */
export const DEGRADED_THRESHOLD = 2;

export function GlobalStatusBanner() {
  const shellStrings = useShellStrings();
  const { view } = useNavigationView();
  const canRead = view.groups.some((g) => g.entries.some((e) => e.key === "health.services"));
  const summary = useQuery({
    queryKey: ["shell", "health-summary"],
    enabled: canRead,
    queryFn: async () =>
      ((await api.GET("/api/v1/services/health")).data as unknown as { items: Array<{ state: string }> })
        .items,
    refetchInterval: 60_000,
    retry: false,
  });
  const failing = (summary.data ?? []).filter(
    (s) => s.state === "unavailable" || s.state === "degraded",
  ).length;
  if (failing < DEGRADED_THRESHOLD) return null;
  return (
    <div className="shell-banner">
      <FunctionalState state="partial" detail={shellStrings.degraded(failing)} />
    </div>
  );
}
