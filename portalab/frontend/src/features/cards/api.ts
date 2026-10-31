import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../../api/client";

/** Issue 229: the media cards — my collection, the sets, a set, a person's cards, my packs. */
export type Rarity = "common" | "rare" | "epic" | "legendary";
export type Variant =
  | "normal"
  | "foil"
  | "showcase"
  | "showcase_foil"
  | "borderless"
  | "borderless_foil"
  | "hd"
  | "genre"
  | "genre_foil";
// from the most common version to the rarest
export const VARIANTS: Variant[] = [
  "normal",
  "foil",
  "genre", // issue 295: its genre's frame
  "genre_foil",
  "showcase",
  "showcase_foil",
  "borderless",
  "borderless_foil",
  "hd",
];
/** Issue 233: a card's edition — the medium of its work's era of release; issue 255: fourteen generations. */
export const EDITIONS = [
  "nitrate",
  "noir",
  "drivein",
  "super8",
  "film",
  "laserdisc",
  "vhs",
  "zine",
  "bubble",
  "disc",
  "leather",
  "tiles",
  "stream",
  "glass",
] as const;
export type Edition = (typeof EDITIONS)[number];

export type Family = "sf" | "action" | "fantasy" | "family" | "drama" | "dark";
/** Issue 295: a work's main genre — its genre frame's. */
export type Genre =
  | "action"
  | "adventure"
  | "animation"
  | "comedy"
  | "crime"
  | "documentary"
  | "drama"
  | "family"
  | "fantasy"
  | "history"
  | "horror"
  | "music"
  | "mystery"
  | "romance"
  | "sf"
  | "thriller"
  | "war"
  | "western";
export interface WorkFacts {
  rating?: number;
  votes?: number;
  budget?: number;
  revenue?: number;
  runtime?: number;
  seasons?: number;
  director?: string;
  genres?: string[];
}

export interface MediaCard {
  id: string;
  set: string;
  set_code: string;
  set_name: string;
  set_size: number;
  set_kind: string;
  /** a scene of the work: behind its people's portraits */
  set_backdrop?: string | null;
  set_poster?: string | null;
  /** the work's genre as the card's colour, and its figures printed on the card (frozen with its set) */
  set_family?: Family;
  set_genre?: Genre;
  set_edition?: Edition | null;
  /** where the face is in each image (its reference: [x, y, its height] as fractions, null: none) */
  focus?: Record<string, [number, number, number?] | null>;
  /** its character cut out of each image (its reference: the cut-out's, null: none) */
  cutout?: Record<string, string | null>;
  set_facts?: WorkFacts;
  set_animated?: boolean;
  /** an actor's place in the credits (0: the lead) */
  billing?: number;
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
  /** a work's card: its full art from an art site (fanart.tv), for its borderless alternative */
  fan_art?: string | null;
  rarity: Rarity;
  retired: boolean;
  owned: Partial<Record<Variant, number>>;
  variant?: Variant;
  copy?: string;
  /** issue 234: drawn in a booster — the member's first copy of it */
  new?: boolean;
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

/** Issue 234: what a content's booster wears — its work's art, its title drawn (logos per language), the season. */
export interface PackLook {
  kind: string | null;
  code: string | null;
  year: number | null;
  family: string;
  edition: Edition | null;
  poster: string | null;
  backdrop: string | null;
  logos: Record<string, string>;
  /** the art site's textless art of the work (its title card's) */
  art?: string | null;
  season: number | null;
  /** a shop's booster: its product (the works it draws among are its family, edition and kind) */
  product?: string | null;
  /** issue 255: the rarity it guarantees */
  rarity?: Rarity | null;
}

export interface CardPack {
  id: string;
  source: string;
  set: string | null;
  set_name: string | null;
  look?: PackLook | null;
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
  if (!ref) return null;
  // an image the cards found and kept themselves (an actor's character, found on the web)
  if (ref.startsWith("blob:")) return `/api/v1/cards/images/${ref.slice(5)}`;
  return `/api/v1/media/metadata-images?ref=${encodeURIComponent(ref)}&size=${size}`;
}

/** An art site's image (fanart.tv) through the portal. */
export function artworkImage(ref: string | null | undefined): string | null {
  return ref ? `/api/v1/media/artwork-images?ref=${encodeURIComponent(ref)}` : null;
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

export function useCardSet(key: string | undefined, { quiet = false }: { quiet?: boolean } = {}) {
  return useQuery({
    queryKey: [...KEY, "set", key],
    enabled: Boolean(key),
    // issue 234: on a work's page, a work without cards is no error
    ...(quiet ? { retry: false } : {}),
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

export function useCardPool(filters: {
  q: string;
  rarity: Rarity | "";
  kind: MediaCard["kind"] | "";
  country: string;
  owned: boolean;
  page: number;
}) {
  return useQuery({
    queryKey: [...KEY, "pool", filters],
    placeholderData: keepPreviousData,
    queryFn: async () =>
      (
        await api.GET("/api/v1/cards/pool", {
          params: {
            // the filters set only (an empty one is no filter)
            query: Object.fromEntries(
              Object.entries(filters).filter(([, value]) => value !== "" && value !== false),
            ) as never,
          },
        })
      ).data as unknown as { total: number; countries: string[]; items: MediaCard[] },
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

/** Issue 229: an administrator's trial pack — six cards among the works whose characters were looked for. */
export function useTrialPack() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      const { data, error } = await api.POST("/api/v1/admin/cards/packs/trial");
      if (error || !data) throw error ?? new Error("trial");
      return data;
    },
    onSettled: () => void client.invalidateQueries({ queryKey: KEY }),
  });
}
