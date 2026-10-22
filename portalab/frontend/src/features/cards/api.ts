import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../../api/client";

/** Issue 229: the media cards — my collection, the sets, a set, a person's cards, my packs. */
export type Rarity = "common" | "rare" | "epic" | "legendary";
export type Variant = "normal" | "foil" | "borderless" | "borderless_foil";
export const VARIANTS: Variant[] = ["normal", "foil", "borderless", "borderless_foil"];

export interface MediaCard {
  id: string;
  set: string;
  set_code: string;
  set_name: string;
  set_size: number;
  set_kind: string;
  year: number | null;
  number: number;
  kind: "title" | "cast" | "director" | "creator" | "writer" | "composer";
  person: string | null;
  name: string;
  role: string | null;
  flavor: string | null;
  art: string | null;
  alt_art: string | null;
  /** an actor's character in this very work: the card's image, its borderless alternative's */
  role_art?: string | null;
  role_alt?: string | null;
  rarity: Rarity;
  retired: boolean;
  owned: Partial<Record<Variant, number>>;
  variant?: Variant;
  copy?: string;
}

export interface CardSetItem {
  key: string;
  code: string;
  name: string;
  kind: string;
  year: number | null;
  poster: string | null;
  saga: string | null;
  size: number;
  owned: number;
}

export interface CardSetDetail extends Omit<CardSetItem, "owned"> {
  present: boolean;
  owned: number;
  cards: MediaCard[];
}

export interface CardPack {
  id: string;
  source: string;
  set: string | null;
  set_name: string | null;
  given_at: string;
  opened_at: string | null;
  cards: MediaCard[];
  count: number;
}

export interface CardsSummary {
  unique: number;
  copies: number;
  sets_started: number;
  cards: number;
  sets: number;
  unopened: number;
}

const KEY = ["cards"] as const;

/** A card's picture through the portal (browsers never call TMDB). */
export function cardImage(ref: string | null | undefined, size = "w500"): string | null {
  return ref ? `/api/v1/media/metadata-images?ref=${encodeURIComponent(ref)}&size=${size}` : null;
}

export function useMyCards() {
  return useQuery({
    queryKey: [...KEY, "me"],
    queryFn: async () => (await api.GET("/api/v1/me/cards")).data as unknown as CardsSummary,
  });
}

export function useCardSets(q: string, started: boolean, page: number) {
  return useQuery({
    queryKey: [...KEY, "sets", q, started, page],
    queryFn: async () =>
      (await api.GET("/api/v1/cards/sets", { params: { query: { q, started, page } } })).data as unknown as {
        total: number;
        items: CardSetItem[];
      },
    placeholderData: keepPreviousData,
  });
}

export function useCardSet(key: string | undefined) {
  return useQuery({
    queryKey: [...KEY, "set", key],
    enabled: Boolean(key),
    queryFn: async () =>
      (await api.GET("/api/v1/cards/sets/{key}", { params: { path: { key: key ?? "" } } }))
        .data as unknown as CardSetDetail,
  });
}

export function useCardPerson(ref: string | null) {
  return useQuery({
    queryKey: [...KEY, "person", ref],
    enabled: Boolean(ref),
    queryFn: async () =>
      (await api.GET("/api/v1/cards/people", { params: { query: { ref: ref ?? "" } } })).data as unknown as {
        ref: string;
        name: string | null;
        art: string | null;
        size: number;
        owned: number;
        cards: MediaCard[];
      },
  });
}

export function usePacks() {
  return useQuery({
    queryKey: [...KEY, "packs"],
    queryFn: async () =>
      (await api.GET("/api/v1/me/cards/packs", { params: { query: { unopened: true } } }))
        .data as unknown as CardPack[],
  });
}

export function useOpenPack() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => {
      const { data, error } = await api.POST("/api/v1/me/cards/packs/{pack_id}/open", {
        params: { path: { pack_id: id } },
      });
      if (error || !data) throw error ?? new Error("open");
      return data as unknown as CardPack;
    },
    onSettled: () => void client.invalidateQueries({ queryKey: KEY }),
  });
}
