import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, CSRF_HEADER, csrfToken } from "../../api/client";
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
  /** 030: where its code runs, and the capabilities approving grants */
  runtime?: "declarative" | "in_process" | "confined";
  requested_capabilities?: Array<{
    capability: string;
    description: string;
    parameters: Record<string, unknown>;
  }>;
}

/** 030: a plugin's confinement, grants, attempts, outgoing calls and secret settings. */
export interface Confinement {
  runtime: string;
  state: string;
  running: boolean;
  confinement: { landlock_abi?: number; seccomp?: boolean; weak?: boolean } | null;
  warning: "unconfined" | "weak" | null;
  requested: Array<{ capability: string; description: string; parameters: Record<string, unknown> }>;
  grants: Array<{ capability: string; description: string; granted_at: string; revoked_at: string | null }>;
  attempts: Array<{ kind: string; detail: Record<string, unknown>; occurred_at: string }>;
  network: {
    hosts: Array<{ host: string; port: number; scheme: string; private: boolean }>;
    last_24h: Record<string, { calls: number; refused: number }>;
  };
  secrets: Array<{ name: string; description: string; set: boolean }>;
}

export function useConfinement(key: string) {
  return useQuery({
    queryKey: [...KEY, "confinement", key],
    queryFn: async () =>
      // biome-ignore lint/suspicious/noExplicitAny: an admin route added by spec 030
      ((await api.GET(`/api/v1/admin/plugins/${key}/confinement` as any, {})).data ??
        null) as Confinement | null,
  });
}

/** PUT a secret setting (write-only), asking once for the confirmation the server requires. */
export async function putSecret(
  key: string,
  name: string,
  value: string,
  confirm: () => boolean,
): Promise<void> {
  const path = `/api/v1/admin/plugins/${key}/secrets/${name}`;
  // biome-ignore lint/suspicious/noExplicitAny: an admin route added by spec 030
  const call = (extra: Record<string, unknown>) => api.PUT(path as any, { body: { value, ...extra } as any });
  try {
    await call({});
  } catch (error) {
    if (error instanceof ApiError && error.code === "authz.confirmation_required" && confirm()) {
      await call({ confirmation: String(error.extensions.confirmation ?? "") });
      return;
    }
    throw error;
  }
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

/** 028 (issue 138): a plugin's .zip sent from the browser — it lands in ``plugins/available`` and is installed
 * awaiting review (its review comes back, to be consented to). */
export function useUploadPlugin() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (file: File) => {
      const token = csrfToken();
      const response = await fetch(`/api/v1/admin/plugins/upload?filename=${encodeURIComponent(file.name)}`, {
        method: "POST",
        credentials: "same-origin",
        headers: {
          "Content-Type": "application/zip",
          ...(token ? { [CSRF_HEADER]: decodeURIComponent(token) } : {}),
        },
        body: file,
      });
      const data = (await response.json().catch(() => ({}))) as Record<string, unknown>;
      if (!response.ok) throw new Error(String(data.detail ?? data.title ?? response.statusText));
      return data as { review: Review };
    },
    onSettled: () => client.invalidateQueries({ queryKey: KEY }),
  });
}
