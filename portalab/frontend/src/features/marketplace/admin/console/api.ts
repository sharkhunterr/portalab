import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { api } from "../../../../api/client";
import type { components } from "../../../../api/generated/schema";
import { useLocaleContext } from "../../../../i18n/provider/I18nProvider";
import { ApiError } from "../../../../state/regions";

/** #98 — the shop's console for administrators: what is going on, members, the catalogue a page at a time. */
export type Overview = components["schemas"]["OverviewOut"];
export type Activity = components["schemas"]["ActivityOut"];
export type EconomySummary = components["schemas"]["EconomySummaryOut"];
export type InventoryItem = components["schemas"]["InventoryItemOut"];
export type CatalogPage = components["schemas"]["CatalogPageOut"];
export interface Season {
  key: string;
  start: readonly number[]; // (month, day)
  end: readonly number[];
  now: boolean;
}
export type LedgerEntry = components["schemas"]["EconomyTransactionOut"];
export type Value = "coins" | "xp" | "contribution";

export interface Member {
  id: string;
  login: string;
  display_name: string | null;
}

const KEY = ["marketplace", "console"] as const;

function fail(error: unknown, response: Response): never {
  if (error instanceof ApiError) throw error;
  throw new ApiError(response.status, response.statusText);
}

/** A product's name in the member's language (else English, else its key). */
export function useNameOf() {
  const { language } = useLocaleContext();
  return (names: Record<string, string> | null | undefined, fallback: string) =>
    names?.[language] ?? names?.[language.split("-")[0] ?? ""] ?? names?.en ?? fallback;
}

export function useOverview(days: number) {
  return useQuery({
    queryKey: [...KEY, "overview", days],
    queryFn: async () => {
      const { data, error, response } = await api.GET("/api/v1/admin/marketplace/overview", {
        params: { query: { days } },
      });
      if (!data) fail(error, response);
      return data;
    },
  });
}

export function useEconomy(days: number) {
  return useQuery({
    queryKey: [...KEY, "economy", days],
    queryFn: async () => {
      const { data, error, response } = await api.GET("/api/v1/admin/economy/summary", {
        params: { query: { days } },
      });
      if (!data) fail(error, response);
      return data;
    },
  });
}

export function useMembers() {
  return useQuery({
    queryKey: [...KEY, "members"],
    staleTime: 60_000,
    queryFn: async () => {
      const { data, error, response } = await api.GET("/api/v1/users", { params: { query: { limit: 100 } } });
      if (!data) fail(error, response);
      return data.items.map((u) => ({
        id: u.id,
        login: u.login,
        display_name: u.display_name ?? null,
      })) as Member[];
    },
  });
}

/** A member's name from their id (the console lists ids). */
export function useMemberName() {
  const members = useMembers();
  const byId = new Map((members.data ?? []).map((m) => [m.id, m]));
  return (id: string) => {
    const member = byId.get(id);
    return member ? (member.display_name ?? member.login) : id.slice(0, 8);
  };
}

export function useCatalogPage(params: { q: string; type: string; state: string; limit: number }) {
  return useQuery({
    queryKey: [...KEY, "catalog", params],
    placeholderData: keepPreviousData,
    queryFn: async () => {
      const { data, error, response } = await api.GET("/api/v1/admin/marketplace/catalog", {
        params: {
          query: {
            limit: params.limit,
            ...(params.q ? { q: params.q } : {}),
            ...(params.type ? { type: params.type } : {}),
            ...(params.state ? { state: params.state as "available" } : {}),
          },
        },
      });
      if (!data) fail(error, response);
      return data;
    },
  });
}

export function useInventory(userId: string | null) {
  return useQuery({
    queryKey: [...KEY, "inventory", userId],
    enabled: Boolean(userId),
    queryFn: async () => {
      const { data, error, response } = await api.GET(
        "/api/v1/admin/marketplace/members/{user_id}/inventory",
        {
          params: { path: { user_id: userId ?? "" } },
        },
      );
      if (!data) fail(error, response);
      return data;
    },
  });
}

export function useLedger(userId: string | null) {
  return useQuery({
    queryKey: [...KEY, "ledger", userId],
    enabled: Boolean(userId),
    queryFn: async () => {
      const { data, error, response } = await api.GET("/api/v1/admin/economy/transactions", {
        params: { query: { user: userId ?? "" } },
      });
      if (!data) fail(error, response);
      return data.items;
    },
  });
}

export function useSeasons() {
  return useQuery({
    queryKey: [...KEY, "seasons"],
    staleTime: 3_600_000,
    queryFn: async () => {
      const { data, error, response } = await api.GET("/api/v1/admin/marketplace/seasons");
      if (!data) fail(error, response);
      return data;
    },
  });
}
