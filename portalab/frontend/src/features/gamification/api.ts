import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../../api/client";
import type { components } from "../../api/generated/schema";

/** Gamification & economy API hooks (spec 013): progression, history, achievements and administration. */
export type Progression = components["schemas"]["ProgressionOut"];
export type EconomyTransaction = components["schemas"]["EconomyTransactionOut"];
export type EconomyTransactionPage = components["schemas"]["EconomyTransactionPage"];
export type RewardRule = components["schemas"]["RewardRuleOut"];
export type Value = "xp" | "contribution" | "coins";

export interface AchievementView {
  key: string;
  state: "locked" | "unlocked" | "hidden";
  label?: string;
  description?: string;
  icon?: string | null;
  unlocked_at?: string | null;
  progress?: Array<{ current: number; target: number }>;
}

export interface AnomalyView {
  id: string;
  user_id: string;
  kind: string;
  window_start: string;
  status: string;
  withheld: Array<{
    id: string;
    value: string;
    amount: number;
    rule: string | null;
    status: string;
    occurred_at: string;
  }>;
}

export interface SimulationResult {
  sample: number;
  matched: boolean;
  grants: Array<{ value: string; base: number; amount: number; factor: number; capped: boolean }>;
}

const KEY = ["gamification"] as const;

export function useProgression() {
  return useQuery({
    queryKey: [...KEY, "progression"],
    queryFn: async () => (await api.GET("/api/v1/me/progression")).data as Progression,
  });
}

export function useTransactions(value: Value | null) {
  return useInfiniteQuery({
    queryKey: [...KEY, "transactions", value],
    initialPageParam: null as string | null,
    getNextPageParam: (last: EconomyTransactionPage) => last.next_cursor,
    queryFn: async ({ pageParam }) =>
      (
        await api.GET("/api/v1/me/economy/transactions", {
          params: { query: { ...(value ? { value } : {}), ...(pageParam ? { cursor: pageParam } : {}) } },
        })
      ).data as EconomyTransactionPage,
  });
}

export function useAchievements() {
  return useQuery({
    queryKey: [...KEY, "achievements"],
    queryFn: async () =>
      ((await api.GET("/api/v1/me/achievements")).data ?? []) as unknown as AchievementView[],
  });
}

// --- admin -------------------------------------------------------------------------------------------
export function useRules() {
  return useQuery({
    queryKey: [...KEY, "rules"],
    queryFn: async () => (await api.GET("/api/v1/admin/gamification/rules")).data ?? [],
  });
}

export function useRuleAdmin() {
  const client = useQueryClient();
  const settle = () => client.invalidateQueries({ queryKey: [...KEY, "rules"] });
  const save = useMutation({
    mutationFn: async ({ key, definition }: { key: string; definition: Record<string, unknown> }) =>
      (
        await api.POST("/api/v1/admin/gamification/rules/{key}", {
          params: { path: { key } },
          body: { definition },
        })
      ).data as RewardRule,
    onSuccess: settle,
  });
  const publish = useMutation({
    mutationFn: async ({ key, version }: { key: string; version: number }) =>
      (
        await api.POST("/api/v1/admin/gamification/rules/{key}/publish", {
          params: { path: { key } },
          body: { version },
        })
      ).data,
    onSuccess: settle,
  });
  const retire = useMutation({
    mutationFn: async (key: string) =>
      (await api.POST("/api/v1/admin/gamification/rules/{key}/retire", { params: { path: { key } } })).data,
    onSuccess: settle,
  });
  const simulate = useMutation({
    mutationFn: async ({
      key,
      definition,
      samples,
    }: {
      key: string;
      definition: Record<string, unknown>;
      samples: Array<Record<string, unknown>>;
    }) =>
      ((
        await api.POST("/api/v1/admin/gamification/rules/{key}/simulate", {
          params: { path: { key } },
          body: { definition, samples },
        })
      ).data ?? []) as unknown as SimulationResult[],
  });
  return { save, publish, retire, simulate };
}

export function useLevelCurve() {
  return useQuery({
    queryKey: [...KEY, "curve"],
    queryFn: async () =>
      (await api.GET("/api/v1/admin/gamification/level-curve")).data as unknown as {
        version: number;
        definition: { base: number; exponent: number };
        preview: Array<{ level: number; xp: number }>;
      },
  });
}

export function usePublishCurve() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (definition: { kind: "power"; base: number; exponent: number }) =>
      (await api.PUT("/api/v1/admin/gamification/level-curve", { body: { definition } })).data,
    onSuccess: () => client.invalidateQueries({ queryKey: [...KEY, "curve"] }),
  });
}

export interface ManualGrant {
  user_id: string;
  value: Value;
  amount: number;
  reason: string;
  confirmation?: string;
}

export function useManualGrant() {
  return useMutation({
    mutationFn: async (body: ManualGrant) =>
      (await api.POST("/api/v1/admin/gamification/manual-grants", { body })).data,
  });
}

export function useAnomalies() {
  return useQuery({
    queryKey: [...KEY, "anomalies"],
    queryFn: async () =>
      ((await api.GET("/api/v1/admin/economy/anomalies")).data ?? []) as unknown as AnomalyView[],
  });
}

export function useAnomalyDecision() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async ({
      id,
      decision,
      reason,
    }: {
      id: string;
      decision: "approve" | "reject" | "confirm-abuse";
      reason: string;
    }) => {
      const options = { params: { path: { flag_id: id } }, body: { reason } };
      if (decision === "approve")
        return (await api.POST("/api/v1/admin/economy/anomalies/{flag_id}/approve", options)).data;
      if (decision === "reject")
        return (await api.POST("/api/v1/admin/economy/anomalies/{flag_id}/reject", options)).data;
      return (await api.POST("/api/v1/admin/economy/anomalies/{flag_id}/confirm-abuse", options)).data;
    },
    onSuccess: () => client.invalidateQueries({ queryKey: [...KEY, "anomalies"] }),
  });
}

export function useVerify() {
  return useMutation({
    mutationFn: async () =>
      (await api.GET("/api/v1/admin/economy/verify")).data as unknown as { ok: boolean; drifts: unknown[] },
  });
}

export type LeaderboardBoard = components["schemas"]["LeaderboardOut"];

export function useLeaderboard(metric: string, period: "all" | "month" | "week") {
  return useQuery({
    queryKey: [...KEY, "leaderboard", metric, period],
    queryFn: async () =>
      (
        await api.GET("/api/v1/leaderboards/{metric}", {
          params: { path: { metric }, query: { period } },
        })
      ).data as LeaderboardBoard,
  });
}
