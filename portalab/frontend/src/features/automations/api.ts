import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../../api/client";
import type { components } from "../../api/generated/schema";

/** Automation API hooks (spec 019, Admin): catalog, definitions, executions, approvals, templates. */
export type Automation = components["schemas"]["AutomationOut"];
export type AutomationDetail = components["schemas"]["AutomationDetailOut"];
export type Execution = components["schemas"]["AutomationExecutionOut"];
export type Approval = components["schemas"]["AutomationApprovalOut"];

export interface Catalog {
  triggers: { events: string[]; schedules: string[] };
  conditions: Array<{ key: string; description: string; params: Record<string, string> }>;
  actions: Array<{
    key: string;
    description: string;
    permission: string;
    params: Record<string, string>;
    required: string[];
    sensitivity: "normal" | "sensitive" | "destructive";
  }>;
}

export interface DryRun {
  conditions_passed: boolean;
  trace: Array<{ leaf: string; result: boolean | "unknown" }>;
  planned_if_passed: Array<{
    id: string;
    action: string;
    allowed?: boolean;
    approval?: boolean;
    params?: unknown;
    status?: string;
  }>;
}

export interface TemplateView {
  key: string;
  title: string;
  description: string;
  valid: boolean;
  errors: string[];
}

const KEY = ["automations"] as const;

export function useCatalog() {
  return useQuery({
    queryKey: [...KEY, "catalog"],
    staleTime: 5 * 60_000,
    queryFn: async () => (await api.GET("/api/v1/admin/automations/catalog")).data as unknown as Catalog,
  });
}

export function useAutomations() {
  return useQuery({
    queryKey: [...KEY, "list"],
    queryFn: async () => (await api.GET("/api/v1/admin/automations")).data ?? [],
  });
}

export function useAutomation(id: string) {
  return useQuery({
    queryKey: [...KEY, "detail", id],
    queryFn: async () =>
      (
        await api.GET("/api/v1/admin/automations/{automation_id}", {
          params: { path: { automation_id: id } },
        })
      ).data as AutomationDetail,
  });
}

export function useExecutions(id: string) {
  return useQuery({
    queryKey: [...KEY, "executions", id],
    queryFn: async () =>
      (
        await api.GET("/api/v1/admin/automations/{automation_id}/executions", {
          params: { path: { automation_id: id } },
        })
      ).data ?? [],
  });
}

export function useApprovals() {
  return useQuery({
    queryKey: [...KEY, "approvals"],
    queryFn: async () => (await api.GET("/api/v1/admin/automations/approvals")).data ?? [],
  });
}

export function useTemplates() {
  return useQuery({
    queryKey: [...KEY, "templates"],
    queryFn: async () =>
      ((await api.GET("/api/v1/admin/automations/templates")).data ?? []) as unknown as TemplateView[],
  });
}

export function useAutomationAdmin() {
  const client = useQueryClient();
  const settle = () => client.invalidateQueries({ queryKey: KEY });
  const create = useMutation({
    mutationFn: async (body: { key: string; definition: Record<string, unknown> }) =>
      (await api.POST("/api/v1/admin/automations", { body })).data as Automation,
    onSuccess: settle,
  });
  const update = useMutation({
    mutationFn: async ({ id, definition }: { id: string; definition: Record<string, unknown> }) =>
      (
        await api.PUT("/api/v1/admin/automations/{automation_id}", {
          params: { path: { automation_id: id } },
          body: { definition },
        })
      ).data,
    onSuccess: settle,
  });
  const publish = useMutation({
    mutationFn: async ({ id, confirmation }: { id: string; confirmation?: string }) =>
      (
        await api.POST("/api/v1/admin/automations/{automation_id}/publish", {
          params: { path: { automation_id: id } },
          body: confirmation ? { confirmation } : {},
        })
      ).data,
    onSuccess: settle,
  });
  const transition = useMutation({
    mutationFn: async ({
      id,
      transition,
    }: {
      id: string;
      transition: "pause" | "resume" | "archive" | "reenable";
    }) =>
      (
        await api.POST("/api/v1/admin/automations/{automation_id}/{transition}", {
          params: { path: { automation_id: id, transition } },
        })
      ).data,
    onSuccess: settle,
  });
  const dryRun = useMutation({
    mutationFn: async ({ id, payload }: { id: string; payload: Record<string, unknown> }) =>
      (
        await api.POST("/api/v1/admin/automations/{automation_id}/dry-run", {
          params: { path: { automation_id: id } },
          body: { payload },
        })
      ).data as unknown as DryRun,
  });
  const decide = useMutation({
    mutationFn: async ({ id, decision }: { id: string; decision: "approve" | "reject" }) => {
      const path = { params: { path: { approval_id: id } } };
      return decision === "approve"
        ? (await api.POST("/api/v1/admin/automations/approvals/{approval_id}/approve", path)).data
        : (await api.POST("/api/v1/admin/automations/approvals/{approval_id}/reject", path)).data;
    },
    onSuccess: settle,
  });
  const instantiate = useMutation({
    mutationFn: async ({ template, key }: { template: string; key: string }) =>
      (
        await api.POST("/api/v1/admin/automations/templates/{template_key}/instantiate", {
          params: { path: { template_key: template } },
          body: { key },
        })
      ).data,
    onSuccess: settle,
  });
  return { create, update, publish, transition, dryRun, decide, instantiate };
}
