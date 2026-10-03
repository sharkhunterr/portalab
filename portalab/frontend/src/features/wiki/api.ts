import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../../api/client";
import type { components } from "../../api/generated/schema";

/** Wiki API hooks (spec 011). */
export type WikiPage = components["schemas"]["WikiPageOut"];
export type WikiPageIn = components["schemas"]["WikiPageIn"];
export type WikiRevision = components["schemas"]["WikiRevisionOut"];
export interface TreeNode {
  id: string;
  slug: string;
  title: string;
  status: string;
  children: TreeNode[];
}
export interface DiffSegment {
  op: "equal" | "insert" | "delete";
  text: string;
}

const KEY = ["wiki"] as const;

export function useTree() {
  return useQuery({
    queryKey: [...KEY, "tree"],
    queryFn: async () => ((await api.GET("/api/v1/wiki/tree")).data ?? []) as unknown as TreeNode[],
  });
}

export function usePage(key: string, lang?: string) {
  return useQuery({
    queryKey: [...KEY, "page", key, lang],
    enabled: Boolean(key),
    retry: false,
    queryFn: async () =>
      (
        await api.GET("/api/v1/wiki/pages/{key}", {
          params: { path: { key }, query: lang ? { lang } : {} },
        })
      ).data as WikiPage,
  });
}

export function useRevisions(pageId: string, enabled = true) {
  return useQuery({
    queryKey: [...KEY, "revisions", pageId],
    enabled: enabled && Boolean(pageId),
    retry: false,
    queryFn: async () =>
      (await api.GET("/api/v1/wiki/pages/{page_id}/revisions", { params: { path: { page_id: pageId } } }))
        .data as WikiRevision[],
  });
}

export async function fetchCompare(pageId: string, from: number, to: number) {
  const { data } = await api.GET("/api/v1/wiki/pages/{page_id}/compare", {
    params: { path: { page_id: pageId }, query: { from, to } },
  });
  return data as unknown as { lines: DiffSegment[]; words: DiffSegment[] };
}

export function useWikiActions() {
  const client = useQueryClient();
  const settle = () => client.invalidateQueries({ queryKey: KEY });
  const create = useMutation({
    mutationFn: async (body: WikiPageIn) => (await api.POST("/api/v1/wiki/pages", { body })).data as WikiPage,
    onSettled: settle,
  });
  const update = useMutation({
    mutationFn: async ({ id, body }: { id: string; body: components["schemas"]["WikiPageUpdateIn"] }) =>
      (await api.PUT("/api/v1/wiki/pages/{page_id}", { params: { path: { page_id: id } }, body }))
        .data as WikiPage,
    onSettled: settle,
  });
  const restore = useMutation({
    mutationFn: async ({ id, version }: { id: string; version: number }) =>
      (
        await api.POST("/api/v1/wiki/pages/{page_id}/restore", {
          params: { path: { page_id: id } },
          body: { version },
        })
      ).data as WikiPage,
    onSettled: settle,
  });
  const publish = useMutation({
    mutationFn: async ({ id, action }: { id: string; action: "publish" | "archive" | "unpublish" }) =>
      (await api.POST("/api/v1/wiki/pages/{page_id}/{action}", { params: { path: { page_id: id, action } } }))
        .data,
    onSettled: settle,
  });
  return { create, update, restore, publish };
}

export function useHelp(key: string | null) {
  return useQuery({
    queryKey: [...KEY, "help", key],
    enabled: Boolean(key),
    staleTime: 5 * 60_000,
    retry: false,
    queryFn: async () =>
      (await api.GET("/api/v1/help", { params: { query: { key: key ?? "" } } })).data ?? [],
  });
}
