import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../../api/client";
import type { components } from "../../api/generated/schema";
import { ApiError } from "../../state/regions";

/** Dashboard API hooks (spec 009): effective dashboard, catalog, per-widget data, writes with If-Match. */
export type DashboardOut = components["schemas"]["DashboardOut"];
export type Instance = components["schemas"]["DashboardInstanceOut"];
export type CatalogEntry = components["schemas"]["CatalogEntryOut"];
export type WidgetPayload = components["schemas"]["WidgetPayloadOut"];

export const DASHBOARD_KEY = ["dashboard"] as const;

export function useDashboard() {
  return useQuery({
    queryKey: DASHBOARD_KEY,
    queryFn: async () => (await api.GET("/api/v1/dashboard")).data as DashboardOut,
  });
}

export function useCatalog(enabled: boolean) {
  return useQuery({
    queryKey: ["dashboard", "catalog"],
    queryFn: async () => ((await api.GET("/api/v1/dashboard/catalog")).data ?? []) as CatalogEntry[],
    enabled,
  });
}

/** One widget's data: its own query, so each frame loads (and fails) independently. */
export function useWidgetData(key: string, instance: string | null, intervalS: number | null) {
  return useQuery({
    queryKey: ["widget", key, instance],
    queryFn: async () =>
      (
        await api.GET("/api/v1/widgets/{key}/data", {
          params: { path: { key }, query: instance ? { instance } : {} },
        })
      ).data as WidgetPayload,
    retry: false,
    staleTime: 30_000,
    ...(intervalS ? { refetchInterval: intervalS * 1000 } : {}),
  });
}

export type Change =
  | { kind: "add"; widget_key: string; config?: Record<string, unknown> }
  | {
      kind: "patch";
      id: string;
      body: {
        status?: "active" | "hidden";
        position?: number;
        w?: number;
        h?: number;
        config?: Record<string, unknown>;
      };
    }
  | { kind: "remove"; id: string }
  | { kind: "layout"; items: Array<{ id: string | null; widget_key: string; w: number; h: number }> };

/** Writes carry the layout version (``If-Match``); a conflict reloads the dashboard and is reported. */
export function useDashboardWrite(onConflict: () => void) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (change: Change) => {
      const current = client.getQueryData<DashboardOut>(DASHBOARD_KEY);
      const headers = current ? { "If-Match": String(current.layout_version) } : undefined;
      switch (change.kind) {
        case "add":
          await api.POST("/api/v1/dashboard/widgets", {
            body: { widget_key: change.widget_key, config: change.config ?? {} },
            ...(headers ? { headers } : {}),
          });
          return;
        case "patch":
          await api.PATCH("/api/v1/dashboard/widgets/{instance_id}", {
            params: { path: { instance_id: change.id } },
            body: change.body,
            ...(headers ? { headers } : {}),
          });
          return;
        case "remove":
          await api.DELETE("/api/v1/dashboard/widgets/{instance_id}", {
            params: { path: { instance_id: change.id } },
            ...(headers ? { headers } : {}),
          });
          return;
        case "layout":
          await api.PUT("/api/v1/dashboard/layout", {
            body: { items: change.items },
            ...(headers ? { headers } : {}),
          });
          return;
      }
    },
    onError: (error) => {
      if (error instanceof ApiError && error.code === "dashboard.version_conflict") onConflict();
    },
    onSettled: async () => {
      await client.invalidateQueries({ queryKey: ["dashboard"] });
    },
  });
}
