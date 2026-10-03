import { useMutation, useQuery } from "@tanstack/react-query";
import { api } from "../../api/client";
import type { components } from "../../api/generated/schema";

/** Shared content API (spec 011): per-viewer link states, render preview, asset upload. */
export type ResolvedLink = components["schemas"]["ContentResolvedLinkOut"];

export function useResolvedLinks(refs: string[]) {
  const key = [...refs].sort();
  return useQuery({
    queryKey: ["content", "links", key],
    enabled: refs.length > 0,
    staleTime: 60_000,
    queryFn: async () => (await api.POST("/api/v1/content/links/resolve", { body: { refs } })).data ?? [],
  });
}

export function usePreview(markdown: string) {
  return useQuery({
    queryKey: ["content", "preview", markdown],
    staleTime: Number.POSITIVE_INFINITY,
    queryFn: async () => (await api.POST("/api/v1/content/render", { body: { markdown } })).data,
  });
}

export function useUploadAsset(ownerRef: string) {
  return useMutation({
    mutationFn: async (file: File) => {
      const { data } = await api.POST("/api/v1/content/assets", {
        params: { query: { owner_ref: ownerRef, filename: file.name } },
        body: file as unknown as string,
        bodySerializer: (body: unknown) => body as BodyInit,
        headers: { "Content-Type": file.type || "application/octet-stream" },
      });
      return data;
    },
  });
}
