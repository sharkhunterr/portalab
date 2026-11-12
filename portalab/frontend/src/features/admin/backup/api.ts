import { useQuery } from "@tanstack/react-query";
import { api, CSRF_COOKIE, CSRF_HEADER, readCookie } from "../../../api/client";
import type { OfferedBlock } from "../arrival/importBlocks";

/** Issue 247 — the portal's backups: the archives, the save or restore running, and an archive sent. */
export interface Archive {
  name: string;
  bytes: number;
  modified_at: string;
}

export interface Run {
  kind: "create" | "restore";
  state: "running" | "done" | "failed";
  phase: string;
  done: number;
  total: number;
  result: Record<string, unknown>;
  error: { code: string; message: string } | null;
}

export interface Inspected {
  name: string;
  site: string;
  created_at: string;
  options: { history?: boolean; media?: boolean };
  counts: { members?: number; services?: number; packs?: number };
  tables: number;
  rows: number;
  folders: { name: string; files: number; bytes: number }[];
  compatible: boolean;
  compatibility: "same" | "older" | "newer";
  portalab: string;
  blocks: OfferedBlock[]; // issue 392: what may be chosen
}

export const BACKUPS_KEY = ["admin", "backups"] as const;

export function useBackups() {
  return useQuery({
    queryKey: BACKUPS_KEY,
    queryFn: async () =>
      (await api.GET("/api/v1/admin/backups")).data as unknown as { archives: Archive[]; run: Run | null },
    refetchInterval: (query) => (query.state.data?.run?.state === "running" ? 1500 : false),
  });
}

/** The share of a run done, 0–100 (the tables, then the files). */
export function percent(run: Run): number {
  if (run.state !== "running") return 100;
  const share = run.total > 0 ? Math.min(1, run.done / run.total) : 0;
  const phases = ["starting", "reading", "schema", "tables", "upgrade", "files", "done"];
  const index = Math.max(0, phases.indexOf(run.phase));
  return Math.round(((index + share) / phases.length) * 100);
}

/** An archive sent to a new portal, its progress told as it goes (the body is the file itself). */
export function uploadArchive(file: File, onProgress: (share: number) => void): Promise<string> {
  return new Promise((resolve, reject) => {
    const request = new XMLHttpRequest();
    request.open("POST", "/api/v1/admin/first-run/import/upload");
    request.withCredentials = true;
    request.setRequestHeader("Content-Type", "application/octet-stream");
    const token = readCookie(CSRF_COOKIE);
    if (token) request.setRequestHeader(CSRF_HEADER, token);
    request.upload.onprogress = (event) => {
      if (event.lengthComputable) onProgress(event.loaded / event.total);
    };
    request.onload = () => {
      if (request.status === 201) resolve((JSON.parse(request.responseText) as { name: string }).name);
      else reject(new Error(String(request.status)));
    };
    request.onerror = () => reject(new Error("network"));
    request.send(file);
  });
}
