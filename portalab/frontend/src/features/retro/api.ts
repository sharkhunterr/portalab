import { useQuery } from "@tanstack/react-query";
import { api, CSRF_HEADER, csrfToken } from "../../api/client";
import type { components } from "../../api/generated/schema";

/** Issue 419: a library's games played in the portal, with the library's own emulator. */
export type RetroGame = components["schemas"]["RetroGameOut"];
export type Sitting = components["schemas"]["SittingOut"];
export type Beat = components["schemas"]["BeatOut"];

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

export async function startSitting(objectId: string): Promise<Sitting> {
  const { data } = await api.POST("/api/v1/retro/games/{object_id}/sittings", {
    params: { path: { object_id: objectId } },
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
