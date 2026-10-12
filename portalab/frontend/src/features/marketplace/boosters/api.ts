import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../../../api/client";
import type { Product } from "../api";

/** #81: the boosters on sale, opening one, the boosters I opened, my reserve and using one of its items. */
export interface Booster {
  key: string;
  names: Record<string, string>;
  descriptions: Record<string, string>;
  price: number;
  cards: number;
  odds: Record<string, number>;
  guarantee: string;
  /** the Coins a duplicate gives back, per rarity (fixed, not the item's price) */
  refunds: Record<string, number>;
  theme: string;
  /** what comes out of it: looks for the collection, or items for the reserve */
  kind: "looks" | "reserve";
  /** a season's: the last day it is on sale */
  until: string | null;
  per_member: number | null;
  /** openings I have left (``null``: no limit) */
  left: number | null;
}

export type Outcome = "new" | "duplicate" | "reserve";

export interface BoosterCard {
  product: Product;
  outcome: Outcome;
  duplicate: boolean;
  refund: number;
}

export interface Opened {
  booster: Booster;
  opening: { id: string; opened_at: string; price: number; refund: number };
  cards: BoosterCard[];
}

export interface PastOpening {
  id: string;
  booster: string;
  names: Record<string, string>;
  opened_at: string;
  price: number;
  refund: number;
  cards: {
    product: string;
    names: Record<string, string>;
    rarity: string | null;
    outcome: Outcome;
    refund: number;
  }[];
}

export interface ReserveEntry {
  product: Product;
  quantity: number;
  /** a ticket: a form to fill once used (a film in 4K, a community project…) */
  needs_configuration: boolean;
}

const KEY = ["marketplace"] as const;

export function useBoosters() {
  return useQuery({
    queryKey: [...KEY, "boosters"],
    queryFn: async () => ((await api.GET("/api/v1/marketplace/boosters")).data ?? []) as unknown as Booster[],
  });
}

/** Opening a booster: its price charged, its cards drawn — the shop, my Coins and my reserve change. */
export function useOpenBooster() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async ({ key, requestKey }: { key: string; requestKey: string }) => {
      const { data, error } = await api.POST("/api/v1/marketplace/boosters/{key}/open", {
        params: { path: { key }, header: { "Idempotency-Key": requestKey } },
      });
      if (error) throw error;
      return data as unknown as Opened;
    },
    onSettled: () => {
      void client.invalidateQueries({ queryKey: KEY });
      // my Coins (the header's chip and the wallet)
      void client.invalidateQueries({ queryKey: ["gamification"] });
      // a look won is worn like a bought one
      void client.invalidateQueries({ queryKey: ["ui", "notification-looks"] });
    },
  });
}

export function useOpenings() {
  return useQuery({
    queryKey: [...KEY, "boosters", "openings"],
    queryFn: async () =>
      ((await api.GET("/api/v1/marketplace/boosters/openings")).data ?? []) as unknown as PastOpening[],
  });
}

export function useReserve() {
  return useQuery({
    queryKey: [...KEY, "reserve"],
    queryFn: async () =>
      ((await api.GET("/api/v1/marketplace/reserve")).data ?? []) as unknown as ReserveEntry[],
  });
}

/** Using an item of my reserve: granted now, it takes effect as if bought. */
export function useUseReserve() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async ({ key, requestKey }: { key: string; requestKey: string }) => {
      const { data, error } = await api.POST("/api/v1/marketplace/reserve/{key}/use", {
        params: { path: { key }, header: { "Idempotency-Key": requestKey } },
      });
      if (error) throw error;
      return data as unknown as { ownership: string; product: string; state: string };
    },
    onSettled: () => {
      void client.invalidateQueries({ queryKey: KEY });
      void client.invalidateQueries({ queryKey: ["gamification"] });
    },
  });
}

/** A name in the reader's language. */
export function localized(map: Record<string, string>, locale: string): string {
  return map[locale.slice(0, 2)] ?? map.en ?? Object.values(map)[0] ?? "";
}

/** A fresh key for one request (a replay of the same request is answered without charging twice). */
export function requestKey(): string {
  return globalThis.crypto?.randomUUID?.() ?? `${Date.now()}-${Math.random().toString(36).slice(2)}`;
}
