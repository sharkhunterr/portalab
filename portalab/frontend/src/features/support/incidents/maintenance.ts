import { useQuery } from "@tanstack/react-query";
import { api } from "../../../api/client";

/** A planned maintenance as members see it (027): on the incidents page and, when asked, as a banner. */
export interface Maintenance {
  id: string;
  service_id: string | null;
  title: string;
  description: string;
  starts_at: string;
  ends_at: string;
  status: string;
  banner?: boolean;
}

export function useMaintenances(enabled = true) {
  return useQuery({
    queryKey: ["maintenance", "upcoming"],
    enabled,
    retry: false,
    refetchInterval: 5 * 60_000,
    queryFn: async () =>
      (
        ((await api.GET("/api/v1/maintenance")).data as unknown as { items: Maintenance[] }).items ?? []
      ).filter((m) => m.status !== "cancelled" && Date.parse(m.ends_at) > Date.now()),
  });
}

export function useServiceNames(enabled = true) {
  return useQuery({
    queryKey: ["services", "names"],
    enabled,
    retry: false,
    staleTime: 10 * 60_000,
    queryFn: async () =>
      new Map(
        (
          (await api.GET("/api/v1/services/health")).data as unknown as {
            items: Array<{ id: string; name: string }>;
          }
        ).items.map((s) => [s.id, s.name]),
      ),
  });
}
