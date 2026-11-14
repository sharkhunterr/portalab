import { useQuery } from "@tanstack/react-query";
import { api, CSRF_HEADER, csrfToken } from "../../api/client";
import type { components } from "../../api/generated/schema";

/** Issue 419: a library's games played in the portal, with the library's own emulator. */
export type RetroGame = components["schemas"]["RetroGameOut"];
export type Sitting = components["schemas"]["SittingOut"];
export type Beat = components["schemas"]["BeatOut"];
export type Progress = components["schemas"]["RetroProgressOut"];
export type SavedState = components["schemas"]["RetroStateOut"];

/** Whether the title plays here (its platform has an emulator, the library has its file) — quiet otherwise. */
export function useRetroGame(objectId: string, enabled = true) {
  return useQuery({
    queryKey: ["retro", "game", objectId],
    enabled: enabled && Boolean(objectId),
    retry: false,
    staleTime: 60_000,
    queryFn: async () => {
      const { data } = await api.GET("/api/v1/retro/games/{object_id}", {
        params: { path: { object_id: objectId } },
      });
      if (!data) throw new Error("empty retro game");
      return data;
    },
  });
}

/** 420: ``resume`` — the save state the game starts from (« Continue »); none: a new game. */
export async function startSitting(objectId: string, resume: number | null = null): Promise<Sitting> {
  const { data } = await api.POST("/api/v1/retro/games/{object_id}/sittings", {
    params: { path: { object_id: objectId } },
    body: { resume },
  });
  if (!data) throw new Error("empty sitting");
  return data;
}

export async function beat(sitting: string): Promise<Beat> {
  const { data } = await api.POST("/api/v1/retro/sittings/{sitting_id}/beat", {
    params: { path: { sitting_id: sitting } },
  });
  return data ?? { minutes_left: null, stop: false };
}

/** ``keepalive`` so the sitting still ends when the page goes away. */
export function endSitting(sitting: string): Promise<Response> {
  const headers: Record<string, string> = {};
  const token = csrfToken();
  if (token) headers[CSRF_HEADER] = token;
  return fetch(`/api/v1/retro/sittings/${sitting}/end`, {
    method: "POST",
    credentials: "include",
    keepalive: true,
    headers,
  });
}

/** EmulatorJS's own translations (« af-FR » is its French). */
const EMULATOR_LANGUAGES: Record<string, string> = {
  en: "en-US",
  fr: "af-FR",
  es: "es-ES",
  de: "de-GER",
  it: "it-IT",
  pt: "pt-BR",
  ja: "ja-JA",
  zh: "zh-CN",
  ru: "ru-RU",
};

export function emulatorLanguage(language: string): string {
  return EMULATOR_LANGUAGES[language.split("-")[0]?.toLowerCase() ?? ""] ?? "en-US";
}

/** The firmware the game starts with: a verified one first (RomM checks them against known hashes). */
export function chooseFirmware(sitting: Sitting): string | null {
  const best = [...sitting.firmware].sort((a, b) => Number(b.verified) - Number(a.verified))[0];
  return best ? best.url : null;
}

/** 420: the player's saves and states in this sitting (slot 0: where the game was left). */
export async function fetchSaves(sitting: string): Promise<Progress> {
  const { data } = await api.GET("/api/v1/retro/sittings/{sitting_id}/saves", {
    params: { path: { sitting_id: sitting } },
  });
  if (!data) throw new Error("empty saves");
  return data;
}

export async function dropState(sitting: string, slot: number): Promise<void> {
  await api.DELETE("/api/v1/retro/sittings/{sitting_id}/states/{slot}", {
    params: { path: { sitting_id: sitting, slot } },
  });
}

/** An emulator's memory (or a picture) kept by the portal, as raw bytes. */
export async function putBytes(url: string, data: Uint8Array | Blob, keepalive = false): Promise<boolean> {
  const headers: Record<string, string> = { "Content-Type": "application/octet-stream" };
  const token = csrfToken();
  if (token) headers[CSRF_HEADER] = token;
  const body = data instanceof Blob ? data : new Blob([data as BlobPart]);
  const response = await fetch(url, { method: "PUT", credentials: "include", keepalive, headers, body });
  return response.ok;
}

export async function getBytes(url: string): Promise<Uint8Array | null> {
  const response = await fetch(url, { credentials: "include" });
  if (!response.ok) return null;
  return new Uint8Array(await response.arrayBuffer());
}

/** A short fingerprint of a save, to send it only when the game changed it. */
export function fingerprint(data: Uint8Array): string {
  let hash = 2166136261;
  for (let i = 0; i < data.length; i += 1) {
    hash ^= data[i] ?? 0;
    hash = Math.imul(hash, 16777619);
  }
  return `${data.length}:${(hash >>> 0).toString(16)}`;
}
