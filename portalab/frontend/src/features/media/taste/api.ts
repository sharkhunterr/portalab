import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../../../api/client";
import type { components } from "../../../api/generated/schema";

/**
 * Issue 190: my taste — the recommendations made for me (each with its reason), the cards to judge one by
 * one, what I said of a title (like, not for me, seen, later) and the lists it makes, my taste as drawn.
 */
export type TasteCard = components["schemas"]["TasteCard"];
export type TasteReason = components["schemas"]["TasteReason"];
export type Verdict = "like" | "dislike" | "seen" | "later";

export interface TasteTrait {
  name: string;
  role: string;
  weight: number;
  works: number;
  titles: string[];
}

export interface TasteProfile {
  genres: TasteTrait[];
  people: TasteTrait[];
  sagas: TasteTrait[];
  themes: TasteTrait[];
  against: { name: string; role: string }[];
  counts: Partial<Record<Verdict, number>>;
  works: number;
  families: string[];
  use_history: boolean;
}

const KEY = ["media", "taste"] as const;

export function useRecommendations(kind?: string, limit = 20) {
  return useQuery({
    queryKey: [...KEY, "recommendations", kind ?? "all", limit],
    staleTime: 5 * 60_000,
    queryFn: async () =>
      (
        await api.GET("/api/v1/me/media/recommendations", {
          params: { query: { ...(kind ? { kind } : {}), limit } },
        })
      ).data?.items ?? [],
  });
}

export function useDeck(limit = 12) {
  return useQuery({
    queryKey: [...KEY, "deck", limit],
    staleTime: Number.POSITIVE_INFINITY, // a new deck only when this one is through
    queryFn: async () =>
      (await api.GET("/api/v1/me/media/taste/deck", { params: { query: { limit } } })).data?.items ?? [],
  });
}

export function useTasteProfile() {
  return useQuery({
    queryKey: [...KEY, "profile"],
    queryFn: async () => (await api.GET("/api/v1/me/media/taste")).data as unknown as TasteProfile,
  });
}

export function useTasteList(verdict: Verdict) {
  return useQuery({
    queryKey: [...KEY, "list", verdict],
    queryFn: async () =>
      (await api.GET("/api/v1/me/media/taste/lists/{verdict}", { params: { path: { verdict } } })).data
        ?.items ?? [],
  });
}

export function useVerdict(objectId: string) {
  return useQuery({
    queryKey: [...KEY, "title", objectId],
    enabled: Boolean(objectId),
    queryFn: async () =>
      ((
        await api.GET("/api/v1/me/media/taste/titles/{object_id}", {
          params: { path: { object_id: objectId } },
        })
      ).data?.verdict ?? null) as Verdict | null,
  });
}

/** Say (or take back, with ``null``) what I think of a title; the lists and recommendations follow. */
export function useJudge() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async ({ objectId, verdict }: { objectId: string; verdict: Verdict | null }) => {
      const path = { object_id: objectId };
      if (verdict === null)
        await api.DELETE("/api/v1/me/media/taste/titles/{object_id}", { params: { path } });
      else
        await api.PUT("/api/v1/me/media/taste/titles/{object_id}", { params: { path }, body: { verdict } });
      return verdict;
    },
    onSuccess: (verdict, { objectId }) => client.setQueryData([...KEY, "title", objectId], verdict),
    onSettled: () =>
      Promise.all(
        ["recommendations", "profile", "list"].map((part) =>
          client.invalidateQueries({ queryKey: [...KEY, part] }),
        ),
      ),
  });
}

export function useForgetTaste() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      await api.DELETE("/api/v1/me/media/taste");
    },
    onSettled: () => client.invalidateQueries({ queryKey: KEY }),
  });
}
