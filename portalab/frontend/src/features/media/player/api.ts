import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, CSRF_COOKIE, CSRF_HEADER, readCookie } from "../../../api/client";
import type { components } from "../../../api/generated/schema";

/** The portal's player API (027, #2): what plays, starting a stream, its subtitles and its timeline. */
export type PlayerInfo = components["schemas"]["PlayerInfoOut"];
export type Playable = components["schemas"]["PlayableItemOut"];
export type PlayerVersion = components["schemas"]["StreamVersionOut"];
export type PlayerTrack = components["schemas"]["StreamTrackOut"];
export type PlayerMarker = components["schemas"]["StreamMarkerOut"];
export type StreamStarted = components["schemas"]["StreamStartOut"];
export type Cue = components["schemas"]["SubtitleCueOut"];
export type StartRequest = components["schemas"]["StreamStartIn"];
export type PlaybackState = "playing" | "paused" | "buffering" | "stopped";

export function usePlayerInfo(objectId: string, item: string | null, enabled = true) {
  return useQuery({
    queryKey: ["media", "player", objectId, item],
    enabled: enabled && Boolean(objectId),
    retry: false,
    staleTime: 0,
    queryFn: async () => {
      const { data } = await api.GET("/api/v1/media/{object_id}/player", {
        params: { path: { object_id: objectId }, query: item ? { item } : {} },
      });
      if (!data) throw new Error("empty player info");
      return data;
    },
  });
}

/** 027: back to zero without playing — the member's resume point on the media server is forgotten. */
export function useResetResume(objectId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (item: string) => {
      await api.POST("/api/v1/media/{object_id}/player/reset", {
        params: { path: { object_id: objectId } },
        body: { item },
      });
    },
    onSuccess: () => client.invalidateQueries({ queryKey: ["media"] }),
  });
}

export async function startStream(objectId: string, body: StartRequest): Promise<StreamStarted> {
  const { data } = await api.POST("/api/v1/media/{object_id}/player/start", {
    params: { path: { object_id: objectId } },
    body,
  });
  if (!data) throw new Error("empty stream");
  return data;
}

/** The media playlist hls.js reads: playlists and segments are relayed by the portal under the ticket. */
export function streamUrl(stream: StreamStarted): string {
  return `/api/v1/media/player/${stream.ticket}/${stream.playlist}`;
}

/** 027 (#13): a chapter's picture, or the server's seek-bar preview at ``at`` seconds. */
export function playerImage(ticket: string, ref: string, at?: number): string {
  const query = new URLSearchParams({ ref });
  if (at !== undefined) query.set("at", String(Math.max(0, at)));
  return `/api/v1/media/player/${ticket}/image?${query}`;
}

export async function fetchCues(ticket: string, at: number, seek: boolean): Promise<Cue[]> {
  const { data } = await api.GET("/api/v1/media/player/{ticket}/subtitles", {
    params: { path: { ticket }, query: { at: Math.max(0, at), seek } },
  });
  return data?.cues ?? [];
}

/** ``keepalive`` so the last position still reaches the server when the page goes away. */
function post(path: string, body?: unknown): Promise<Response> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  const token = readCookie(CSRF_COOKIE);
  if (token) headers[CSRF_HEADER] = token;
  return fetch(path, {
    method: "POST",
    credentials: "include",
    keepalive: true,
    headers,
    ...(body === undefined ? {} : { body: JSON.stringify(body) }),
  });
}

export function reportTimeline(
  ticket: string,
  state: PlaybackState,
  position: number,
  duration: number | null,
): Promise<Response> {
  return post(`/api/v1/media/player/${ticket}/timeline`, {
    state,
    position_s: Math.max(0, position),
    ...(duration ? { duration_s: duration } : {}),
  });
}

export function stopStream(ticket: string): Promise<Response> {
  return post(`/api/v1/media/player/${ticket}/stop`);
}
