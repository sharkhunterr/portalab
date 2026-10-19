import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../../../api/client";
import type { Product } from "../api";

/** #81: what a booster holds — on its product (``product.booster``) and in the shelf of boosters. */
export interface BoosterInfo {
  cards: number;
  /** the odds per rarity, in % */
  odds: Record<string, number>;
  /** the weights the administrators set (the odds before they are brought to 100 %) */
  weights: Record<string, number>;
  guarantee: string;
  /** the Coins a duplicate gives back, per rarity (fixed, not the item's price) */
  refunds: Record<string, number>;
  pool: "looks" | "hd" | "reserve";
  /** what comes out of it: looks for the collection, or items for the reserve */
  kind: "looks" | "reserve";
  season: string | null;
  /** issue 130: the packs it draws from (a collection's booster) */
  packs?: string[];
  /** and the items it draws, named one by one */
  items?: string[];
  /** whether it names what it may draw (one saved before that rule: ``false``, to define) */
  defined?: boolean;
  /** a season's: the last day it is on sale */
  until: string | null;
  per_member: number | null;
  /** its pack's look */
  look: string;
}

/** #81: a booster of the shop, with what is mine about it. */
export interface Booster extends BoosterInfo {
  key: string;
  names: Record<string, string>;
  descriptions: Record<string, string>;
  price: number;
  rarity: string;
  theme: string;
  /** on sale now (a season's only in its weeks) */
  on_sale: boolean;
  /** openings I have left (``null``: no limit) */
  left: number | null;
  /** sealed ones I keep (offered — a level reward, an achievement — or bought): opened for free */
  sealed: number;
}

/** A booster product's info (``product.booster``). */
export function boosterOf(product: Product): BoosterInfo | null {
  return (product as Product & { booster?: BoosterInfo | null }).booster ?? null;
}

export type Outcome = "new" | "duplicate" | "reserve";

export interface BoosterCard {
  product: Product;
  outcome: Outcome;
  duplicate: boolean;
  refund: number;
  /** won before its level or Contribution: held, usable once they are reached */
  locked: boolean;
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
    locked?: boolean;
  }[];
}

export interface ReserveEntry {
  product: Product;
  quantity: number;
  /** a ticket: a form to fill once used (a film in 4K, a community project…) */
  needs_configuration: boolean;
  /** a sealed booster: opened, not used */
  booster: boolean;
  /** issue 131: a level pass, used on an item waiting for its level */
  early_unlock?: boolean;
}

const KEY = ["marketplace"] as const;

export function useBoosters(enabled = true) {
  return useQuery({
    queryKey: [...KEY, "boosters"],
    enabled,
    queryFn: async () => ((await api.GET("/api/v1/marketplace/boosters")).data ?? []) as unknown as Booster[],
  });
}

/** Opening a booster — bought now, or a sealed one I keep: its cards drawn; the shop, my Coins and my
 * reserve change. */
export function useOpenBooster() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async ({ key, requestKey, sealed }: { key: string; requestKey: string; sealed: boolean }) => {
      const { data, error } = await api.POST("/api/v1/marketplace/boosters/{key}/open", {
        params: { path: { key }, query: { sealed }, header: { "Idempotency-Key": requestKey } },
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

/** issue 131: spend a level pass on an item I hold that waits for its level — wearable at once. */
export function useEarlyUnlock() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async ({ key, target }: { key: string; target: string }) => {
      const { data, error } = await api.POST("/api/v1/marketplace/reserve/{key}/unlock", {
        params: { path: { key } },
        body: { target },
      });
      if (error) throw error;
      return data as unknown as { ownership: string; product: string; state: string };
    },
    onSettled: () => {
      void client.invalidateQueries({ queryKey: KEY });
      void client.invalidateQueries({ queryKey: ["ui", "notification-looks"] });
      void client.invalidateQueries({ queryKey: ["marketplace", "profile-looks"] });
    },
  });
}

/** Open a booster on the stage, wherever one is (the shop's sheet, the reserve). */
export const BOOSTER_EVENT = "portalab:booster-open";
export function openBooster(key: string, sealed = false): void {
  window.dispatchEvent(new CustomEvent(BOOSTER_EVENT, { detail: { key, sealed } }));
}

/** A name in the reader's language. */
export function localized(map: Record<string, string>, locale: string): string {
  return map[locale.slice(0, 2)] ?? map.en ?? Object.values(map)[0] ?? "";
}

/** A fresh key for one request (a replay of the same request is answered without charging twice). */
export function requestKey(): string {
  return globalThis.crypto?.randomUUID?.() ?? `${Date.now()}-${Math.random().toString(36).slice(2)}`;
}
