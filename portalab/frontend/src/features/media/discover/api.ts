import { useQuery } from "@tanstack/react-query";
import { api } from "../../../api/client";
import type { Metadata } from "../detail/Enrichment";

/** #4: what one can ask for (the request service's search, shelves and details) and #3 my quota. */
export interface Requestable {
  tmdb_id: string;
  kind: "movie" | "series";
  title: string;
  year: number | null;
  overview: string | null;
  poster: string | null;
  backdrop: string | null;
  rating: number | null;
  release_date: string | null;
  status: "unknown" | "pending" | "processing" | "partial" | "available";
  object_id: string | null;
  request: { mine: boolean } | null;
  route: string;
}

export interface RequestableSeason {
  number: number;
  name: string | null;
  episodes: number | null;
  air_date: string | null;
  status: Requestable["status"];
}

export interface RequestableDetails extends Requestable {
  genres: string[];
  runtime: number | null;
  tagline: string | null;
  cast: Array<{ name: string; character: string | null; profile: string | null }>;
  trailer: string | null;
  ids: Record<string, string>;
  seasons: RequestableSeason[];
  /** the request service has a 4K server for this kind */
  four_k: boolean;
  /** the enriched details, in the library metadata's shape */
  metadata: Partial<Metadata>;
}

export type DiscoverShelf =
  | "trending"
  | "popular_movies"
  | "popular_series"
  | "upcoming_movies"
  | "upcoming_series";

export interface QuotaWindow {
  limit: number | null;
  days: number | null;
  used: number;
  remaining: number | null;
  restricted: boolean;
  renews_at: string | null;
}

export interface RequestQuota {
  base_limit: number;
  base_used: number;
  base_remaining: number;
  extra_units: number;
  period: string;
  service:
    | { linked: false }
    | { linked: true; available: false }
    | { linked: true; available: true; movie: QuotaWindow; tv: QuotaWindow }
    | null;
}

const KEY = ["media", "discover"] as const;

export function useDiscoverShelf(name: DiscoverShelf) {
  return useQuery({
    queryKey: [...KEY, "shelf", name],
    staleTime: 5 * 60_000,
    retry: false,
    queryFn: async () =>
      (await api.GET("/api/v1/media/discover/shelves/{name}", { params: { path: { name } } }))
        .data as unknown as { items: Requestable[]; configured: boolean },
  });
}

export function useDiscoverSearch(q: string) {
  return useQuery({
    queryKey: [...KEY, "search", q],
    enabled: q.trim().length > 1,
    retry: false,
    queryFn: async () =>
      (await api.GET("/api/v1/media/discover/search", { params: { query: { q } } })).data as unknown as {
        items: Requestable[];
        configured: boolean;
      },
  });
}

export function useDiscoverTitle(kind: string, tmdb: string, enabled = true) {
  return useQuery({
    queryKey: [...KEY, "title", kind, tmdb],
    enabled: enabled && Boolean(tmdb),
    retry: false,
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/media/discover/{kind}/{tmdb_id}", {
        params: { path: { kind, tmdb_id: tmdb } },
      });
      if (error) throw error;
      return data as unknown as RequestableDetails;
    },
  });
}

export function useRequestQuota() {
  return useQuery({
    queryKey: ["media", "quota"],
    retry: false,
    staleTime: 30_000,
    queryFn: async () => (await api.GET("/api/v1/me/media/requests/quota")).data as unknown as RequestQuota,
  });
}

/** How many requests of this kind I may still make now (``null``: no limit), bought units included. */
export function requestsLeft(quota: RequestQuota | undefined, kind: "movie" | "series"): number | null {
  if (!quota) return null;
  const service = quota.service;
  if (service && service.linked && "movie" in service) {
    const window = kind === "movie" ? service.movie : service.tv;
    if (!window.limit) return null;
    return Math.max(0, window.remaining ?? 0) + quota.extra_units;
  }
  return quota.base_remaining + quota.extra_units;
}
