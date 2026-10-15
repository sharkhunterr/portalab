import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, CSRF_COOKIE, CSRF_HEADER } from "../../api/client";
import { ACTIVE_VISUALS_KEY } from "../../design-system/themes/external/ExternalVisualsLoader";
import type { ExternalElement } from "../../design-system/themes/external/external";

/** issue 1 (POC): the administration of imported visual packs. */

export interface Summary {
  blocking: number;
  warning: number;
  info: number;
  elements: number;
  hd: boolean;
  script: boolean;
  publishable: boolean;
}

export interface VersionRow {
  version: string;
  sha: string;
  status: "pending" | "approved" | "rejected";
  detected_at: string | null;
  summary: Summary;
  names: Record<string, string> | null;
  author: string | null;
  license: string | null;
  decision: Record<string, unknown> | null;
  simulated: boolean;
}

export interface PackRow {
  id: string;
  source: { kind: string; path?: string; url?: string } | null;
  current: string | null;
  enabled: boolean;
  remote: { version: string; ref: string; release: boolean; checked_at: string } | null;
  versions: VersionRow[];
}

export interface Finding {
  level: "blocking" | "warning" | "info";
  code: string;
  element: string | null;
  params: Record<string, unknown>;
}

export interface ElementReport {
  folder: string;
  product: string;
  type: string;
  look: string | null;
  kind: string;
  hd: boolean;
  script: boolean;
  names: Record<string, string>;
  descriptions: Record<string, string>;
  economy: Economy;
  payload: Record<string, unknown>;
  bytes: number;
}

export interface Economy {
  price: number | null;
  rarity: string;
  level: number | null;
  supply: number | null;
  collection: string | null;
  icon: string | null;
}

export interface VersionDetail {
  pack: string;
  version: string;
  sha: string;
  status: string;
  report: {
    summary: Summary;
    items: Finding[];
    elements: ElementReport[];
    pack: Record<string, unknown> | null;
  };
  simulation: { at: string; results: SimulationResult[] } | null;
  decision: { economy?: Record<string, Partial<Economy>> } | null;
  elements: ExternalElement[];
}

export interface SimulationResult {
  product: string;
  ok: boolean;
  detail?: string;
  fps?: number;
}

const LIST = ["visuals", "admin"] as const;

export function useVisualPacks() {
  return useQuery({
    queryKey: LIST,
    queryFn: async () =>
      (await api.GET("/api/v1/admin/visuals")).data as unknown as { packs: PackRow[]; inbox: string },
  });
}

export function useVersionDetail(pack: string | null, version: string | null) {
  return useQuery({
    queryKey: ["visuals", "detail", pack, version],
    enabled: Boolean(pack && version),
    queryFn: async () =>
      (
        await api.GET("/api/v1/admin/visuals/{pack}/{version}", {
          params: { path: { pack: pack as string, version: version as string } },
        })
      ).data as unknown as VersionDetail,
  });
}

/** Any of the administration's calls: the list, the detail and what members load follow. */
export function useVisualAction() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async ({ path, body, raw }: { path: string; body?: unknown; raw?: Blob }) => {
      const token = document.cookie
        .split("; ")
        .find((part) => part.startsWith(`${CSRF_COOKIE}=`))
        ?.slice(CSRF_COOKIE.length + 1);
      const response = await fetch(path, {
        method: "POST",
        credentials: "same-origin",
        headers: {
          "Content-Type": raw ? "application/zip" : "application/json",
          ...(token ? { [CSRF_HEADER]: decodeURIComponent(token) } : {}),
        },
        body: raw ?? JSON.stringify(body ?? {}),
      });
      const text = await response.text();
      const data = text ? (JSON.parse(text) as Record<string, unknown>) : {};
      if (!response.ok) throw new Error(String(data.detail ?? data.title ?? response.statusText));
      return data;
    },
    onSettled: () => {
      void client.invalidateQueries({ queryKey: ["visuals"] });
      void client.invalidateQueries({ queryKey: ACTIVE_VISUALS_KEY });
      void client.invalidateQueries({ queryKey: ["marketplace"] });
    },
  });
}
