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
