import { useQuery } from "@tanstack/react-query";
import { api, CSRF_COOKIE, CSRF_HEADER, readCookie } from "../../../api/client";
import type { components } from "../../../api/generated/schema";

/** #20, #21: listening to an audiobook and reading a book in the portal. */
export type ListenInfo = components["schemas"]["ListenOut"];
export type AudioInfo = components["schemas"]["AudioItemOut"];
export type AudioChapter = components["schemas"]["AudioChapterOut"];
export type AudioTrack = components["schemas"]["AudioTrackOut"];
export type ReadInfo = components["schemas"]["ReadOut"];
export type BookFormat = components["schemas"]["BookFormatOut"];
export type ReadingPosition = components["schemas"]["ReadingPositionOut"];
export type SessionState = "playing" | "paused" | "stopped" | "finished";

export async function fetchListen(objectId: string): Promise<ListenInfo> {
  const { data } = await api.GET("/api/v1/media/{object_id}/listen", {
    params: { path: { object_id: objectId } },
  });
  if (!data) throw new Error("empty listening info");
  return data;
}

/** What the title's page needs to offer « Listen »: fetched only for audiobooks. */
export function useListenInfo(objectId: string, enabled: boolean) {
  return useQuery({
    queryKey: ["media", "listen", objectId],
    enabled: enabled && Boolean(objectId),
    retry: false,
    staleTime: 0,
    queryFn: () => fetchListen(objectId),
  });
}

export function useReadInfo(objectId: string, enabled = true) {
  return useQuery({
    queryKey: ["media", "read", objectId],
    enabled: enabled && Boolean(objectId),
    retry: false,
    staleTime: 0,
    queryFn: async () => {
      const { data } = await api.GET("/api/v1/media/{object_id}/read", {
        params: { path: { object_id: objectId } },
      });
      if (!data) throw new Error("empty reading info");
      return data;
    },
  });
}

/** The audio of the open audiobook (one of its files when it has several), relayed with byte ranges. */
export function audioUrl(ticket: string, track: number | null): string {
  return `/api/v1/media/listen/${ticket}/audio${track === null ? "" : `?track=${track}`}`;
}

export function fileUrl(ticket: string, fileRef: string): string {
  return `/api/v1/media/read/${ticket}/file/${fileRef}`;
}

export function pageUrl(ticket: string, fileRef: string, page: number): string {
  return `/api/v1/media/read/${ticket}/page/${fileRef}/${page}`;
}

export async function fetchPages(ticket: string, fileRef: string): Promise<number[]> {
  const response = await fetch(`/api/v1/media/read/${ticket}/pages/${fileRef}`, { credentials: "include" });
  if (!response.ok) throw new Error(`pages: HTTP ${response.status}`);
  const body = (await response.json()) as { pages: number[] };
  return body.pages;
}

/** ``keepalive`` so the last position still reaches the server when the page goes away. */
function post(path: string, body: unknown): Promise<Response> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  const token = readCookie(CSRF_COOKIE);
  if (token) headers[CSRF_HEADER] = token;
  return fetch(path, {
    method: "POST",
    credentials: "include",
    keepalive: true,
    headers,
    body: JSON.stringify(body),
  });
}

export function reportListening(
  ticket: string,
  state: SessionState,
  position: number,
  duration: number | null,
  track: number | null,
  seq: number,
): Promise<Response> {
  return post(`/api/v1/media/listen/${ticket}/position`, {
    state,
    position_s: Math.max(0, position),
    ...(duration ? { duration_s: duration } : {}),
    ...(track === null ? {} : { track }),
    seq,
  });
}

export function reportReading(
  ticket: string,
  body: {
    state: SessionState;
    format: string;
    file_ref: string | null;
    position: string;
    percent: number;
    seconds: number;
    seq: number;
  },
): Promise<Response> {
  return post(`/api/v1/media/read/${ticket}/position`, {
    ...body,
    percent: Math.min(1, Math.max(0, body.percent)),
    ...(body.file_ref ? {} : { file_ref: undefined }),
  });
}

/** « 1 h 05 », « 12:34 » */
export function clock(seconds: number): string {
  const s = Math.max(0, Math.floor(seconds));
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = s % 60;
  const pad = (n: number) => String(n).padStart(2, "0");
  return h ? `${h}:${pad(m)}:${pad(sec)}` : `${m}:${pad(sec)}`;
}
