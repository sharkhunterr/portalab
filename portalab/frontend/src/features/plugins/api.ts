import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../../api/client";
import type { components } from "../../api/generated/schema";
import { ApiError } from "../../state/regions";

/** Plugin and module administration (spec 023). */
export type PluginRow = components["schemas"]["PluginOut"];

export interface Review {
  key: string;
  name: string;
  version: string;
  scope: string;
  maturity: string;
  code: boolean;
  permissions: string[];
  extension_points: string[];
  events: { produces: string[]; consumes: string[] };
  personal_data: boolean;
  schema: string;
  sha256: string;
}

export interface Discovered {
  package: string;
  valid: boolean;
  key?: string;
  name?: string;
  version?: string;
  maturity?: string;
  deprecation_notice?: string | null;
  state?: string | null;
  installed_version?: string | null;
  compatibility?: string[];
  dependencies?: string[];
}

export interface ModuleRow {
  key: string;
  enabled: boolean;
  requires: string[];
  essential: boolean;
  needs_restart: boolean;
}

const KEY = ["plugins"] as const;

export function usePlugins() {
  return useQuery({
    queryKey: [...KEY, "list"],
    queryFn: async () => ((await api.GET("/api/v1/admin/plugins")).data ?? []) as PluginRow[],
  });
}

export function useDiscovery() {
  return useQuery({
    queryKey: [...KEY, "discovery"],
    queryFn: async () =>
      ((await api.GET("/api/v1/admin/plugins/discovery")).data ?? []) as unknown as Discovered[],
  });
}

export function usePluginDetail(key: string | null) {
  return useQuery({
    queryKey: [...KEY, "detail", key],
    enabled: key !== null,
    queryFn: async () => {
      const path = { params: { path: { key: key ?? "" } } };
      const [detail, diagnostics] = await Promise.all([
        api.GET("/api/v1/admin/plugins/{key}", path),
        api.GET("/api/v1/admin/plugins/{key}/diagnostics", path),
      ]);
      return {
        detail: detail.data as unknown as {
          plugin: PluginRow;
          review: Review;
          dependencies: string[];
          dependents: string[];
          deprecation_notice?: string | null;
        },
        diagnostics: diagnostics.data as unknown as {
          contributions: Array<{ point: string; id: string; state: string }>;
          conflicts: Array<{ point: string; id: string; detail: string | null }>;
          errors: Array<{ window_start: string; kind: string; count: number; last: string | null }>;
        },
      };
    },
  });
}

/** POST to an admin plugin action; asks once for the confirmation the server requires. */
async function post(path: string, body: Record<string, unknown>, confirm: () => boolean): Promise<unknown> {
  const call = (extra: Record<string, unknown>) =>
    // biome-ignore lint/suspicious/noExplicitAny: one generic call for the admin plugin actions
    api.POST(path as any, { body: { ...body, ...extra } as any });
  try {
    return (await call({})).data;
  } catch (error) {
    if (error instanceof ApiError && error.code === "authz.confirmation_required" && confirm()) {
      return (await call({ confirmation: String(error.extensions.confirmation ?? "") })).data;
    }
    throw error;
  }
}

export function usePluginActions() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async ({
      path,
      body = {},
      confirm = () => true,
    }: {
      path: string;
      body?: Record<string, unknown>;
      confirm?: () => boolean;
    }) => post(path, body, confirm),
    onSuccess: () => client.invalidateQueries({ queryKey: KEY }),
  });
}

export function useModules() {
  return useQuery({
    queryKey: [...KEY, "modules"],
    queryFn: async () => ((await api.GET("/api/v1/admin/modules")).data ?? []) as unknown as ModuleRow[],
  });
}
