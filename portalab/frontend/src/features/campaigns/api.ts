import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../../api/client";
import type { components } from "../../api/generated/schema";

export type CampaignPresentation = components["schemas"]["CampaignPresentationOut"];
export type Campaign = components["schemas"]["CampaignOut"];

export interface CampaignView {
  key: string;
  name: string;
  description: string;
  state: string;
  timezone: string;
  windows: Array<{ start_at: string; end_at: string }>;
  modifiers: Array<{
    value: string;
    factor: number;
    kinds?: string[];
    genres?: string[];
    activities?: string[];
    titles?: string[];
    everyone?: boolean;
  }>;
  /** 027: shop reductions while it runs, and its own achievements and quests. */
  discounts?: Array<{
    percent: number;
    products: number;
    categories: string[];
    seasons?: string[];
    everything?: boolean;
  }>;
  achievements?: Array<{ key: string; label: string }>;
  quests?: Array<{ key: string; label: string }>;
}

export interface CampaignHistory {
  versions: Array<{ version: number; effective_from: string }>;
  occurrences: Array<{ id: string; index: number; start_at: string; end_at: string; status: string }>;
  intervals: Array<{
    opened_at: string | null;
    closed_at: string | null;
    version: number;
    cause: string;
    reason: string | null;
  }>;
  overrides: Array<{
    kind: string;
    from_at: string;
    until_at: string | null;
    reason: string;
    expired_at: string | null;
  }>;
}

export interface SimulationRow {
  modifier: string;
  value: string;
  factor: number;
  version: number;
  verdict: "match" | "no_match" | "unknown" | "audience";
  source_ref: string;
}

const KEY = ["campaigns"] as const;

export function useActiveCampaigns() {
  return useQuery({
    queryKey: [...KEY, "active"],
    staleTime: 60_000,
    queryFn: async () => (await api.GET("/api/v1/campaigns/active")).data ?? [],
  });
}

export function usePresentation(enabled = true) {
  return useQuery({
    queryKey: [...KEY, "presentation"],
    enabled,
    staleTime: 5 * 60_000,
    retry: false,
    queryFn: async () =>
      (await api.GET("/api/v1/campaigns/active/presentation")).data as CampaignPresentation,
  });
}

export function useCampaign(key: string) {
  return useQuery({
    queryKey: [...KEY, "view", key],
    queryFn: async () =>
      (await api.GET("/api/v1/campaigns/{key}", { params: { path: { key } } }))
        .data as unknown as CampaignView,
  });
}

export function useCampaignsAdmin() {
  return useQuery({
    queryKey: [...KEY, "admin"],
    queryFn: async () => (await api.GET("/api/v1/admin/campaigns")).data ?? [],
  });
}

export function useHistory(id: string | null) {
  return useQuery({
    queryKey: [...KEY, "history", id],
    enabled: id !== null,
    queryFn: async () =>
      (
        await api.GET("/api/v1/admin/campaigns/{campaign_id}/history", {
          params: { path: { campaign_id: id as string } },
        })
      ).data as unknown as CampaignHistory,
  });
}

export type CampaignAction = "activate" | "deactivate" | "cancel";

export function useCampaignAdmin() {
  const client = useQueryClient();
  const settle = () => client.invalidateQueries({ queryKey: KEY });
  const create = useMutation({
    mutationFn: async (body: { key: string; definition: Record<string, unknown> }) =>
      (await api.POST("/api/v1/admin/campaigns", { body: { ...body, draft: false } })).data,
    onSuccess: settle,
  });
  const publish = useMutation({
    mutationFn: async ({
      id,
      definition,
      confirmation,
    }: {
      id: string;
      definition: Record<string, unknown>;
      confirmation?: string;
    }) =>
      (
        await api.PUT("/api/v1/admin/campaigns/{campaign_id}", {
          params: { path: { campaign_id: id } },
          body: { definition, ...(confirmation ? { confirmation } : {}) },
        })
      ).data,
    onSuccess: settle,
  });
  const act = useMutation({
    mutationFn: async ({
      id,
      action,
      reason,
      confirmation,
    }: {
      id: string;
      action: CampaignAction;
      reason: string;
      confirmation?: string;
    }) => {
      const options = {
        params: { path: { campaign_id: id } },
        body: { reason, ...(confirmation ? { confirmation } : {}) },
      };
      if (action === "activate")
        return (await api.POST("/api/v1/admin/campaigns/{campaign_id}/activate", options)).data;
      if (action === "deactivate")
        return (await api.POST("/api/v1/admin/campaigns/{campaign_id}/deactivate", options)).data;
      return (await api.POST("/api/v1/admin/campaigns/{campaign_id}/cancel", options)).data;
    },
    onSuccess: settle,
  });
  const archive = useMutation({
    mutationFn: async (id: string) =>
      (
        await api.POST("/api/v1/admin/campaigns/{campaign_id}/archive", {
          params: { path: { campaign_id: id } },
        })
      ).data,
    onSuccess: settle,
  });
  const simulate = useMutation({
    mutationFn: async ({
      id,
      event_type,
      payload,
    }: {
      id: string;
      event_type: string;
      payload: Record<string, unknown>;
    }) =>
      ((
        await api.POST("/api/v1/admin/campaigns/{campaign_id}/simulate", {
          params: { path: { campaign_id: id } },
          body: { event_type, payload },
        })
      ).data ?? []) as unknown as SimulationRow[],
  });
  return { create, publish, act, archive, simulate };
}

/** What a shop reduction covers, in words: « the whole shop », « Christmas items », « 9 items »… */
export function discountScope(
  t: (key: string, values?: Record<string, string | number>) => string,
  d: {
    everything?: boolean | undefined;
    seasons?: string[] | undefined;
    categories: string[] | number;
    products: number;
  },
): string {
  if (d.everything) return t("campaigns:discount.everything");
  const categories = typeof d.categories === "number" ? d.categories : d.categories.length;
  const parts = [
    ...(d.seasons ?? []).map((s) =>
      t("campaigns:discount.season", { season: t(`campaigns:editor.season.${s}`) }),
    ),
    ...(categories ? [t("campaigns:discount.categories", { count: categories })] : []),
    ...(d.products ? [t("campaigns:discount.products", { count: d.products })] : []),
  ];
  return parts.join(" + ") || t("campaigns:discount.products", { count: 0 });
}
