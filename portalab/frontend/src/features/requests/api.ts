import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../../api/client";

/**
 * Issue 363: the members' requests for titles no service asks for (a book, an audiobook, a game…) — what may
 * be asked for, my requests and the open ones I may want too, the administrators' queue. Every call answers
 * « unavailable » while the module is switched off: the pages and the buttons leading to them hide.
 */
export type AskStatus = "new" | "accepted" | "in_progress" | "available" | "refused" | "cancelled";
export const OPEN: readonly AskStatus[] = ["new", "accepted", "in_progress"];

export interface Asked {
  id: string;
  kind: string;
  title: string;
  creators: string[];
  year: number | null;
  details: Record<string, string>;
  ids: Record<string, string[]>;
  note: string | null;
  status: AskStatus;
  reason: string | null;
  supporters: number;
  mine: boolean;
  asked: boolean;
  route: string | null;
  object_id: string | null;
  created_at: string;
  updated_at: string;
  // the administrators': who wants it
  requester?: string | null;
  wanted_by?: { name: string; asked: boolean; since: string }[];
}

export interface Quota {
  limit: number;
  days: number;
}

export interface AskOptions {
  kinds: string[];
  price: number;
  left: Record<string, number | null>;
  quotas: Record<string, Quota>;
}

export interface AskInput {
  kind: string;
  title: string;
  creators: string[];
  year: number | null;
  details: Record<string, string>;
  ids: Record<string, string[]>;
  note: string | null;
}

export interface AskConfig {
  kinds: string[];
  quotas: Record<string, Quota>;
  price: number;
}

export interface AskQueue {
  key: string;
  config: AskConfig;
  known_kinds: string[];
  statuses: AskStatus[];
  figures: Partial<Record<AskStatus, number>>;
  requests: Asked[];
}

const MINE = ["requests", "mine"] as const;

/** What may be asked for — ``undefined`` (and no error shown) while the module is switched off. */
export function useAskOptions() {
  return useQuery({
    queryKey: ["requests", "options"],
    retry: false,
    staleTime: 60_000,
    queryFn: async () => (await api.GET("/api/v1/requests/options")).data as unknown as AskOptions,
  });
}

export function useMyAsks() {
  return useQuery({
    queryKey: MINE,
    retry: false,
    queryFn: async () =>
      (await api.GET("/api/v1/requests")).data as unknown as { mine: Asked[]; open: Asked[] },
  });
}

export function useAskActions() {
  const client = useQueryClient();
  const done = () => client.invalidateQueries({ queryKey: ["requests"] });
  return {
    ask: useMutation({
      mutationFn: async (body: AskInput) =>
        (await api.POST("/api/v1/requests", { body: body as never })).data as unknown as Asked,
      onSuccess: done,
    }),
    support: useMutation({
      mutationFn: async (id: string) =>
        (await api.POST("/api/v1/requests/{request_id}/support", { params: { path: { request_id: id } } }))
          .data as unknown as Asked,
      onSuccess: done,
    }),
    withdraw: useMutation({
      mutationFn: async (id: string) =>
        api.DELETE("/api/v1/requests/{request_id}/support", { params: { path: { request_id: id } } }),
      onSuccess: done,
    }),
  };
}

export function useAskQueue(status: AskStatus | "all") {
  return useQuery({
    queryKey: ["requests", "queue", status],
    retry: false,
    queryFn: async () =>
      (
        await api.GET("/api/v1/admin/requests", {
          params: { query: (status === "all" ? {} : { status }) as never },
        })
      ).data as unknown as AskQueue,
  });
}

export interface Decision {
  id: string;
  status: Exclude<AskStatus, "cancelled">;
  reason?: string;
  object_id?: string;
}

export function useDecide() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, ...body }: Decision) =>
      (
        await api.POST("/api/v1/admin/requests/{request_id}/decision", {
          params: { path: { request_id: id } },
          body: body as never,
        })
      ).data as unknown as Asked,
    onSuccess: () => client.invalidateQueries({ queryKey: ["requests"] }),
  });
}

export function useSaveAskConfig() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (config: AskConfig) =>
      api.PUT("/api/v1/admin/config", {
        body: {
          changes: [{ key: "requests.config", value: config, scope: "global", scope_ref: "", unset: false }],
          reason: "requests: settings",
        } as never,
      }),
    onSuccess: () => client.invalidateQueries({ queryKey: ["requests"] }),
  });
}
