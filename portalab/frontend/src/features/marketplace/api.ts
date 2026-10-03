import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../../api/client";
import type { components } from "../../api/generated/schema";

/** Community project funding API (spec 015, slice A). */
export type Project = components["schemas"]["ProjectOut"];
export type ProjectFunding = components["schemas"]["ProjectFundingOut"];

const KEY = ["marketplace"] as const;

export function useProjects(state?: string) {
  return useQuery({
    queryKey: [...KEY, "projects", state ?? "all"],
    queryFn: async () =>
      ((await api.GET("/api/v1/projects", { params: { query: state ? { state } : {} } })).data ??
        []) as Project[],
  });
}

export function useProject(projectId: string) {
  return useQuery({
    queryKey: [...KEY, "project", projectId],
    queryFn: async () =>
      (await api.GET("/api/v1/projects/{project_id}", { params: { path: { project_id: projectId } } }))
        .data as Project,
  });
}

export function useMyFundings() {
  return useQuery({
    queryKey: [...KEY, "fundings"],
    queryFn: async () => ((await api.GET("/api/v1/me/fundings")).data ?? []) as ProjectFunding[],
  });
}

export function useFund(projectId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async ({ amount, requestKey }: { amount: number; requestKey: string }) =>
      (
        await api.POST("/api/v1/projects/{project_id}/fund", {
          params: { path: { project_id: projectId }, header: { "Idempotency-Key": requestKey } },
          body: { amount, acknowledged: true },
        })
      ).data as ProjectFunding,
    onSuccess: () => client.invalidateQueries({ queryKey: KEY }),
  });
}

export type AdminAction = "promote" | "open" | "validate" | "transition" | "abandon" | "reject";

export function useProjectAdmin() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async ({
      projectId,
      action,
      body,
    }: {
      projectId: string;
      action: AdminAction;
      body: Record<string, unknown>;
    }) => {
      const path =
        `/api/v1/admin/projects/${projectId}/${action}` as "/api/v1/admin/projects/{project_id}/promote";
      // biome-ignore lint/suspicious/noExplicitAny: one generic call for the six admin transitions
      const result = await api.POST(path, { params: { path: { project_id: projectId } }, body: body as any });
      return result.data as Project;
    },
    onSuccess: () => client.invalidateQueries({ queryKey: KEY }),
  });
}

// --- slice B: catalog ------------------------------------------------------------------------------------
export type Product = components["schemas"]["MarketplaceProductOut"];
export type OwnershipRow = components["schemas"]["MarketplaceOwnershipOut"];
export type Category = components["schemas"]["MarketplaceCategoryOut"];

export function useCategories() {
  return useQuery({
    queryKey: [...KEY, "categories"],
    queryFn: async () => ((await api.GET("/api/v1/marketplace/categories")).data ?? []) as Category[],
  });
}

export function useProducts(filters: { category?: string; q?: string }) {
  return useQuery({
    queryKey: [...KEY, "products", filters],
    queryFn: async () =>
      ((
        await api.GET("/api/v1/marketplace/products", {
          params: {
            query: {
              ...(filters.category ? { category: filters.category } : {}),
              ...(filters.q ? { q: filters.q } : {}),
            },
          },
        })
      ).data ?? []) as Product[],
  });
}

export function useProduct(key: string) {
  return useQuery({
    queryKey: [...KEY, "product", key],
    retry: false,
    queryFn: async () =>
      (await api.GET("/api/v1/marketplace/products/{key}", { params: { path: { key } } })).data as Product,
  });
}

export function useAcquire(key: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (requestKey: string) =>
      (
        await api.POST("/api/v1/marketplace/products/{key}/acquire", {
          params: { path: { key }, header: { "Idempotency-Key": requestKey } },
        })
      ).data as OwnershipRow,
    onSuccess: () => client.invalidateQueries({ queryKey: KEY }),
  });
}

export function usePurchases() {
  return useQuery({
    queryKey: [...KEY, "purchases"],
    queryFn: async () => ((await api.GET("/api/v1/me/marketplace/purchases")).data ?? []) as OwnershipRow[],
  });
}

export function useOwnedActions() {
  const client = useQueryClient();
  const refresh = () => client.invalidateQueries({ queryKey: KEY });
  return {
    configure: useMutation({
      mutationFn: async ({ id, configuration }: { id: string; configuration: Record<string, unknown> }) =>
        (
          await api.POST("/api/v1/me/marketplace/owned/{ownership_id}/configure", {
            params: { path: { ownership_id: id } },
            body: { configuration },
          })
        ).data,
      onSuccess: refresh,
    }),
    refund: useMutation({
      mutationFn: async ({ id, reason }: { id: string; reason: string }) =>
        (
          await api.POST("/api/v1/me/marketplace/owned/{ownership_id}/refund", {
            params: { path: { ownership_id: id } },
            body: { reason },
          })
        ).data,
      onSuccess: refresh,
    }),
  };
}
