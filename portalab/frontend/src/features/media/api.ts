import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../../api/client";
import type { components } from "../../api/generated/schema";
import { ApiError } from "../../state/regions";

/** Media API hooks (spec 024): catalog, detail sections, shelves, playback, requests, links, admin. */
export type MediaCard = components["schemas"]["MediaCard"];
export type MediaSection = components["schemas"]["MediaSectionOut"];
export type ShelfName = "new" | "released" | "recent" | "continue" | "trending" | "recommended" | "leaving";

export interface CatalogFilters {
  q?: string;
  kind?: string;
  genre?: string;
  year?: number;
  availability?: "available" | "unavailable";
  /** issue 111: a span of years, each kind's own fields, what I already watched, read or played, the order */
  year_from?: number;
  year_to?: number;
  author?: string;
  narrator?: string;
  director?: string;
  platform?: string;
  publisher?: string;
  series?: string;
  language?: string;
  seen?: "unseen" | "started" | "finished";
  sort?: "title" | "added" | "year";
}
export type CatalogFacets = components["schemas"]["MediaFacets"];

const KEY = ["media"] as const;

export { ApiError as MediaError } from "../../state/regions";

/** Problem documents already throw ``ApiError`` (client middleware); this covers an empty success body. */
function fail(_error: unknown, response: Response): never {
  throw new ApiError(response.status, response.statusText);
}

export function imageUrl(id: string | null | undefined): string | null {
  return id ? `/api/v1/media/images/${id}` : null;
}

export function useCatalogPage(filters: CatalogFilters) {
  return useInfiniteQuery({
    queryKey: [...KEY, "catalog", filters],
    initialPageParam: null as string | null,
    getNextPageParam: (last: components["schemas"]["MediaPage"]) => last.next_cursor,
    queryFn: async ({ pageParam }) => {
      const { data, error, response } = await api.GET("/api/v1/media", {
        params: {
          query: {
            ...Object.fromEntries(Object.entries(filters).filter(([, v]) => v !== undefined && v !== "")),
            ...(pageParam ? { cursor: pageParam } : {}),
          },
        },
      });
      if (!data) fail(error, response);
      return data;
    },
  });
}

/** Issue 111: what the catalog's filters offer for a kind — genres, years, people, platforms… */
export function useCatalogFacets(kind: string | undefined) {
  return useQuery({
    queryKey: [...KEY, "facets", kind ?? ""],
    staleTime: 10 * 60_000,
    queryFn: async () => {
      const { data, error, response } = await api.GET("/api/v1/media/facets", {
        params: { query: kind ? { kind } : {} },
      });
      if (!data) fail(error, response);
      return data;
    },
  });
}

export function useMediaDetail(id: string) {
  return useQuery({
    queryKey: [...KEY, "detail", id],
    retry: false,
    queryFn: async () => {
      const { data, error, response } = await api.GET("/api/v1/media/{object_id}", {
        params: { path: { object_id: id } },
      });
      if (!data) fail(error, response);
      return data;
    },
  });
}

export type Person = components["schemas"]["PersonOut"];

/** #92: a person's page — an actor's, a director's, an author's, a narrator's titles in the library. */
export function personPath(name: string): string {
  return `/media/people/${encodeURIComponent(name)}`;
}

export function usePerson(name: string) {
  return useQuery({
    queryKey: [...KEY, "person", name],
    retry: false,
    queryFn: async () => {
      const { data, error, response } = await api.GET("/api/v1/media/person", {
        params: { query: { name } },
      });
      if (!data) fail(error, response);
      return data;
    },
  });
}

/** Issue 361: a collection — a film's saga, a book's series, a game's franchise — and the one a title is in. */
export type Collection = components["schemas"]["CollectionOut"];

export function collectionPath(ref: string): string {
  return `/media/collection?ref=${encodeURIComponent(ref)}`;
}

export function useTitleCollection(objectId: string) {
  return useQuery({
    queryKey: [...KEY, "collection-of", objectId],
    retry: false,
    staleTime: 5 * 60_000,
    queryFn: async () => {
      const { data, error, response } = await api.GET("/api/v1/media/{object_id}/collection", {
        params: { path: { object_id: objectId } },
      });
      if (error) fail(error, response);
      return (data ?? null) as Collection | null;
    },
  });
}

export function useCollection(ref: string) {
  return useQuery({
    queryKey: [...KEY, "collection", ref],
    retry: false,
    enabled: ref !== "",
    queryFn: async () => {
      const { data, error, response } = await api.GET("/api/v1/media/collection", {
        params: { query: { ref } },
      });
      if (!data) fail(error, response);
      return data;
    },
  });
}

export function useSection(id: string, name: string) {
  return useQuery({
    queryKey: [...KEY, "section", id, name],
    retry: false,
    queryFn: async () => {
      const { data, error, response } = await api.GET("/api/v1/media/{object_id}/sections/{name}", {
        params: { path: { object_id: id, name } },
      });
      if (!data) fail(error, response);
      return data;
    },
  });
}

export function useShelf(shelf: ShelfName) {
  return useQuery({
    queryKey: [...KEY, "shelf", shelf],
    queryFn: async () => {
      const { data, error, response } = await api.GET("/api/v1/media/discovery/{shelf}", {
        params: { path: { shelf } },
      });
      if (!data) fail(error, response);
      return data;
    },
  });
}

export function useNowPlaying() {
  return useQuery({
    queryKey: [...KEY, "now-playing"],
    refetchInterval: 30_000,
    queryFn: async () => (await api.GET("/api/v1/me/media/now-playing")).data ?? [],
  });
}

export function useRequestActions() {
  const client = useQueryClient();
  const settle = () => client.invalidateQueries({ queryKey: KEY });
  const submit = useMutation({
    mutationFn: async (body: components["schemas"]["MediaRequestIn"]) => {
      const { data, error, response } = await api.POST("/api/v1/media/requests", { body });
      if (!data) fail(error, response);
      return data;
    },
    onSettled: settle,
  });
  const cancel = useMutation({
    mutationFn: async (id: string) => {
      const { data, error, response } = await api.POST("/api/v1/media/requests/{request_id}/cancel", {
        params: { path: { request_id: id } },
      });
      if (!data) fail(error, response);
      return data;
    },
    onSettled: settle,
  });
  return { submit, cancel };
}

export function useLinks() {
  return useQuery({
    queryKey: [...KEY, "links"],
    queryFn: async () => (await api.GET("/api/v1/me/media/links")).data ?? [],
  });
}

export function useLinkActions() {
  const client = useQueryClient();
  const settle = () => client.invalidateQueries({ queryKey: [...KEY, "links"] });
  const add = useMutation({
    mutationFn: async (body: components["schemas"]["MediaLinkIn"]) => {
      const { data, error, response } = await api.POST("/api/v1/me/media/links", { body });
      if (!data) fail(error, response);
      return data;
    },
    onSettled: settle,
  });
  const verify = useMutation({
    mutationFn: async ({ id, proof }: { id: string; proof: string }) => {
      const { data, error, response } = await api.POST("/api/v1/me/media/links/{link_id}/verify", {
        params: { path: { link_id: id } },
        body: { proof },
      });
      if (!data) fail(error, response);
      return data;
    },
    onSettled: settle,
  });
  const remove = useMutation({
    mutationFn: (id: string) =>
      api.DELETE("/api/v1/me/media/links/{link_id}", { params: { path: { link_id: id } } }),
    onSettled: settle,
  });
  return { add, verify, remove };
}

export function useCandidates() {
  return useQuery({
    queryKey: [...KEY, "admin", "candidates"],
    queryFn: async () => {
      const { data, error, response } = await api.GET("/api/v1/admin/media/match-candidates");
      if (!data) fail(error, response);
      return data;
    },
  });
}

export function useAdminActions() {
  const client = useQueryClient();
  const settle = () => client.invalidateQueries({ queryKey: [...KEY, "admin"] });
  const merge = useMutation({
    mutationFn: async (body: components["schemas"]["MediaMergeIn"]) => {
      const { data, error, response } = await api.POST("/api/v1/admin/media/merge", { body });
      if (!data) fail(error, response);
      return data;
    },
    onSettled: settle,
  });
  const reject = useMutation({
    mutationFn: (id: string) =>
      api.POST("/api/v1/admin/media/match-candidates/{candidate_id}/reject", {
        params: { path: { candidate_id: id } },
      }),
    onSettled: settle,
  });
  return { merge, reject };
}
