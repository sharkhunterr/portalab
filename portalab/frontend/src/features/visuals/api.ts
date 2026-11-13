import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, CSRF_HEADER, csrfToken } from "../../api/client";
import { ACTIVE_VISUALS_KEY } from "../../design-system/visuals/ExternalVisualsLoader";
import type { ExternalElement } from "../../design-system/visuals/registry";

/** 028: the administration of visual packs — their registry and the six steps of a version. */

export type Step =
  | "imported"
  | "analysed"
  | "tested"
  | "reviewed"
  | "published"
  | "refused"
  | "superseded"
  | "purged";
export type Outcome = "done" | "warning" | "blocking";
export type PackState = "enabled" | "disabled" | "archived";

export interface Summary {
  blocking: number;
  warning: number;
  info: number;
  elements: number;
  hd: boolean;
  /** issue 287: a part played as a video */
  video?: boolean;
  script: boolean;
  publishable: boolean;
  security?: { blocking: number; warning: number; info: number };
}

export interface Confirmations {
  scripts: boolean;
  replaces: string[];
  contracts: string[];
}

export interface Decision {
  by?: string | null;
  at?: string;
  economy?: Record<string, Partial<Economy>>;
  confirmations?: Partial<Confirmations>;
  reason?: string;
  trusted?: boolean;
}

export interface VersionRow {
  version: string;
  sha: string;
  step: Step;
  outcomes: Partial<Record<"import" | "analysis" | "security" | "test" | "review" | "validation", Outcome>>;
  summary: Summary | null;
  names: Record<string, string> | null;
  author: string | null;
  license: string | null;
  decision: Decision | null;
  tested: boolean;
  detected_at: string | null;
  published_at: string | null;
  ever_published: boolean;
}

export interface PackRow {
  id: string;
  names: Record<string, string>;
  builtin: boolean;
  socle: boolean;
  source: { kind: string; path?: string; url?: string } | null;
  state: PackState;
  current: string | null;
  remote: { version: string; ref: string; release: boolean; checked_at: string } | null;
  update: boolean;
  versions: VersionRow[];
  /** how many times its elements failed in members' pages (a script not answering, or breaking) */
  failures?: number;
  /** 028: what it brings for the dashboard — widgets, widget looks and options (its live version's) */
  widgets?: PackWidgetElement[];
}

export interface PackWidgetElement {
  product: string;
  type: "widget" | "widget_style" | "widget_option";
  look: string | null;
  kind: string;
  names: Record<string, string>;
  widget: {
    for?: string | null;
    setting?: string;
    value?: string;
    place?: string | null;
    sizes?: unknown[];
  } | null;
  contracts: string[];
  sold: boolean;
  price: number | null;
  rarity: string;
}

export interface Finding {
  level: "blocking" | "warning" | "info";
  code: string;
  category: "analysis" | "security";
  element: string | null;
  params: Record<string, unknown>;
}

export interface Economy {
  price: number | null;
  rarity: string;
  level: number | null;
  supply: number | null;
  collection: string | null;
  icon: string | null;
  season?: string | null;
  /** 028 (US6): ``false`` — given to everyone, never a shop product (widgets, their looks and options) */
  sold?: boolean;
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
  replaces?: boolean;
  contracts?: string[];
  bytes: number;
}

export interface Measure {
  element: string;
  kind: string;
  compiled?: boolean;
  fps?: number;
  ready_ms?: number;
  errors?: string[];
}

export interface VersionDetail extends VersionRow {
  pack: string;
  builtin: boolean;
  current: boolean;
  report: {
    summary: Summary;
    items: Finding[];
    elements: ElementReport[];
    pack: Record<string, unknown> | null;
  };
  measures: { at: string; by: string | null; results: Measure[] } | null;
  draft: { economy?: Record<string, Partial<Economy>>; confirmations?: Partial<Confirmations> } | null;
  changes: { added?: string[]; removed?: string[]; changed?: string[] } | null;
  elements: ExternalElement[];
}

export const VISUALS = ["visuals", "admin"] as const;

export function useVisualPacks() {
  return useQuery({
    queryKey: VISUALS,
    queryFn: async () =>
      (await api.GET("/api/v1/admin/visuals")).data as unknown as { packs: PackRow[]; inbox: string },
  });
}

export function useVersionDetail(pack: string | undefined, version: string | undefined) {
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

/** An error the API answered (its own words, and its code for the interface to translate). */
export class VisualsError extends Error {
  readonly code: string | null;

  constructor(message: string, code: string | null) {
    super(message);
    this.code = code;
  }
}

/** Any of the administration's calls: the list, the detail and what members load follow. */
export function useVisualAction() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async ({
      path,
      body,
      raw,
      method = "POST",
    }: {
      path: string;
      body?: unknown;
      raw?: Blob;
      method?: "POST" | "PUT";
    }) => {
      const token = csrfToken();
      const response = await fetch(path, {
        method,
        credentials: "same-origin",
        headers: {
          "Content-Type": raw ? "application/zip" : "application/json",
          ...(token ? { [CSRF_HEADER]: decodeURIComponent(token) } : {}),
        },
        body: raw ?? JSON.stringify(body ?? {}),
      });
      const text = await response.text();
      const data = text ? (JSON.parse(text) as Record<string, unknown>) : {};
      if (!response.ok) {
        throw new VisualsError(
          String(data.detail ?? data.title ?? response.statusText),
          typeof data.code === "string" ? data.code : null,
        );
      }
      return data;
    },
    onSettled: () => {
      void client.invalidateQueries({ queryKey: ["visuals"] });
      void client.invalidateQueries({ queryKey: ACTIVE_VISUALS_KEY });
      void client.invalidateQueries({ queryKey: ["marketplace"] });
    },
  });
}

/** The administration's address of a pack (and of one of its versions). */
export function packPath(pack: string, version?: string): string {
  const head = `/api/v1/admin/visuals/${encodeURIComponent(pack)}`;
  return version ? `${head}/${encodeURIComponent(version)}` : head;
}

/** The step a version waits at: the first not done yet (its last one once published or closed). */
export function nextStep(version: Pick<VersionRow, "step" | "outcomes">): StepKey {
  const { step, outcomes } = version;
  if (step === "published" || step === "superseded") return "validation";
  if (step === "refused" || step === "purged") return "validation";
  if (outcomes.analysis === "blocking") return "analysis";
  if (outcomes.security === "blocking") return "security";
  if (step === "analysed") return "test";
  if (step === "tested") return "review";
  return "validation";
}

export const STEPS = ["import", "analysis", "security", "test", "review", "validation"] as const;
export type StepKey = (typeof STEPS)[number];

/** 028 (US6): a data contract packs' widgets may ask for, as the portal describes it. */
export interface WidgetContract {
  key: string;
  permission: string;
  refresh_s: number;
  fields: string[];
  descriptions: Record<string, string>;
}

/** Every dashboard widget's data, offered as a contract (``widget:<key>``). */
export interface WidgetDataContract {
  key: string;
  widget: string;
  title_key: string;
  permission: string;
}

export function useWidgetContracts(enabled = true) {
  return useQuery({
    queryKey: ["visuals", "contracts"],
    enabled,
    staleTime: 10 * 60_000,
    queryFn: async () =>
      (await api.GET("/api/v1/admin/visuals/contracts")).data as unknown as {
        contracts: WidgetContract[];
        widgets: WidgetDataContract[];
      },
  });
}
