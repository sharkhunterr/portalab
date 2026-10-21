import { useQuery } from "@tanstack/react-query";
import { api } from "../../../api/client";
import type { components } from "../../../api/generated/schema";

export type Radio = components["schemas"]["RadioOut"];
export type RadioTrack = components["schemas"]["RadioTrackOut"];
export type RadioRequest = components["schemas"]["RadioRequestOut"];

export const RADIO_KEY = ["media", "radio"] as const;

/** Issue 168: what the radio plays — refreshed every 20 s while shown. */
export function useRadio(enabled = true) {
  return useQuery({
    queryKey: RADIO_KEY,
    enabled,
    refetchInterval: 20_000,
    retry: false,
    queryFn: async () => (await api.GET("/api/v1/media/radio")).data as Radio,
  });
}

export function coverUrl(track: RadioTrack | null | undefined): string | null {
  return track?.cover_ref ? `/api/v1/media/radio/covers/${encodeURIComponent(track.cover_ref)}` : null;
}

export async function askRadio(text: string): Promise<RadioRequest> {
  const { data } = await api.POST("/api/v1/media/radio/requests", { body: { text } });
  return data as RadioRequest;
}

export async function radioRequest(id: string): Promise<RadioRequest> {
  const { data } = await api.GET("/api/v1/media/radio/requests/{request_id}", {
    params: { path: { request_id: id } },
  });
  return data as RadioRequest;
}
