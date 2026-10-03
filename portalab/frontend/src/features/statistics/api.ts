import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../../api/client";
import type { components } from "../../api/generated/schema";

/** Statistics API hooks (spec 017): catalog, one statistic, hidden sections, Wrapped. */
export type CatalogEntry = components["schemas"]["StatisticsCatalogEntryOut"];
export type StatResult = components["schemas"]["StatResultOut"];
export type PeriodKind = "day" | "week" | "month" | "quarter" | "year" | "last_n_days";

export interface StatQuery {
  key: string;
  period: PeriodKind;
  days?: number;
  filters?: Record<string, string>;
}

export function useCatalog() {
  return useQuery({
    queryKey: ["statistics", "catalog"],
    queryFn: async () => ((await api.GET("/api/v1/statistics/catalog")).data ?? []) as CatalogEntry[],
  });
}

export function useStatistic(query: StatQuery, enabled = true) {
  return useQuery({
    queryKey: ["statistics", "one", query],
    enabled,
    retry: false,
    staleTime: 60_000,
    queryFn: async () =>
      (
        await api.GET("/api/v1/statistics/{key}", {
          params: {
            path: { key: query.key },
            query: {
              period: query.period,
              ...(query.period === "last_n_days" ? { days: query.days ?? 30 } : {}),
              filter: Object.entries(query.filters ?? {}).map(([name, value]) => `${name}:${value}`),
            },
          },
        })
      ).data as StatResult,
  });
}

export function useHiddenSections() {
  const client = useQueryClient();
  const query = useQuery({
    queryKey: ["statistics", "hidden"],
    queryFn: async () =>
      ((await api.GET("/api/v1/me/statistics/preferences")).data as { hidden: string[] } | undefined)
        ?.hidden ?? [],
  });
  const save = useMutation({
    mutationFn: async (hidden: string[]) => {
      await api.PUT("/api/v1/me/statistics/preferences", { body: { hidden } });
    },
    onSettled: async () => {
      await client.invalidateQueries({ queryKey: ["statistics"] });
    },
  });
  return { hidden: query.data ?? [], save };
}

export interface Snapshot {
  id: string;
  wrapped_key: string;
  period_start: string;
  period_end: string;
  scope: string;
  payload: { version: number; stats: StatResult[] };
  generated_at: string;
}

export function useMyWrapped() {
  return useQuery({
    queryKey: ["statistics", "wrapped"],
    queryFn: async () => ((await api.GET("/api/v1/me/wrapped")).data ?? []) as unknown as Snapshot[],
  });
}
