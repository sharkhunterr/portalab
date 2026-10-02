import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../../api/client";
import type { components } from "../../api/generated/schema";

/** Search API hooks (spec 008 T017): classic search, history and palette resolution (TanStack Query). */
export type SearchOut = components["schemas"]["SearchOut"];
export type GroupOut = components["schemas"]["SearchGroupOut"];
export type ItemOut = components["schemas"]["SearchItemOut"];
export type HistoryOut = components["schemas"]["SearchHistoryOut"];
export type Mode = "exact" | "semantic" | "mixed";

export interface SearchParams {
  q: string;
  mode: Mode;
  kinds: string[];
  filters: Record<string, string[]>;
}

export async function runSearch(params: SearchParams, cursor?: string | null): Promise<SearchOut> {
  const { data } = await api.POST("/api/v1/search", {
    body: {
      q: params.q,
      mode: params.mode,
      filters: params.filters,
      kinds: params.kinds.length ? params.kinds : null,
      cursor: cursor ?? null,
    },
  });
  return data as SearchOut;
}

export function useSearch(params: SearchParams) {
  const active = params.q.trim() !== "" || params.kinds.length > 0 || Object.keys(params.filters).length > 0;
  return useQuery({
    queryKey: ["search", params],
    queryFn: () => runSearch(params),
    enabled: active,
    placeholderData: keepPreviousData, // applying a filter keeps the page in place (FR-011)
    retry: false,
  });
}

export function useHistory() {
  return useQuery({
    queryKey: ["search", "history"],
    queryFn: async () => ((await api.GET("/api/v1/me/search-history")).data ?? []) as HistoryOut[],
    retry: false,
  });
}

export function useHistoryActions() {
  const client = useQueryClient();
  const refresh = () => client.invalidateQueries({ queryKey: ["search", "history"] });
  const remove = useMutation({
    mutationFn: async (id: string) => {
      await api.DELETE("/api/v1/me/search-history/{entry_id}", { params: { path: { entry_id: id } } });
    },
    onSuccess: refresh,
  });
  const clear = useMutation({
    mutationFn: async () => {
      await api.DELETE("/api/v1/me/search-history");
    },
    onSuccess: refresh,
  });
  return { remove, clear };
}

export interface PaletteEntry {
  id: string;
  label: string;
  kind: "navigate" | "action";
  route: string | null;
  action_id: string | null;
  sensitivity: string;
  confirmation_required: boolean;
  keywords: string[];
}

export interface PaletteResolution {
  destinations: PaletteEntry[];
  actions: PaletteEntry[];
  object: { kind: string; id: string; title: string; route: string } | null;
  intent: {
    type: "navigate" | "search" | "command";
    target: string | null;
    query: string | null;
    route: string | null;
  } | null;
  suggestions: Array<{
    label: string;
    route: string | null;
    command_key: string | null;
    query: string | null;
  }>;
  assistant: "off" | "ok" | "unavailable";
}

export async function resolvePalette(q: string, route: string): Promise<PaletteResolution> {
  const { data } = await api.GET("/api/v1/palette/resolve", { params: { query: { q, route } } });
  return data as unknown as PaletteResolution;
}

export async function suggest(
  q: string,
): Promise<Array<{ kind: string; id: string; title: string; url_ref: string }>> {
  const { data } = await api.GET("/api/v1/search/suggest", { params: { query: { q } } });
  return ((data as unknown as { items?: unknown[] })?.items ?? []) as Array<{
    kind: string;
    id: string;
    title: string;
    url_ref: string;
  }>;
}

/** Label of a result group: ``search.kind.users`` → catalog ``search:kind.users``. */
export function kindKey(labelKey: string): string {
  return `search:${labelKey.replace(/^search\./, "")}`;
}
