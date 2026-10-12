import { useMutation, useQuery } from "@tanstack/react-query";
import { api } from "../../../api/client";
import type { Product } from "../api";

/** #81 (proof of concept): the boosters on sale and a reveal (visual only). */
export interface Booster {
  key: string;
  names: Record<string, string>;
  descriptions: Record<string, string>;
  price: number;
  cards: number;
  odds: Record<string, number>;
  guarantee: string;
  theme: string;
}

export interface BoosterCard {
  product: Product;
  duplicate: boolean;
  refund: number;
}

export interface Reveal {
  booster: Booster;
  cards: BoosterCard[];
  preview: boolean;
}

export function useBoosters() {
  return useQuery({
    queryKey: ["marketplace", "boosters"],
    queryFn: async () => ((await api.GET("/api/v1/marketplace/boosters")).data ?? []) as unknown as Booster[],
  });
}

export function useReveal() {
  return useMutation({
    mutationFn: async (key: string) => {
      const { data, error } = await api.POST("/api/v1/marketplace/boosters/{key}/reveal", {
        params: { path: { key } },
      });
      if (error) throw error;
      return data as unknown as Reveal;
    },
  });
}

/** A booster's name in the reader's language. */
export function localized(map: Record<string, string>, locale: string): string {
  return map[locale.slice(0, 2)] ?? map.en ?? Object.values(map)[0] ?? "";
}
