import { useQuery } from "@tanstack/react-query";
import { api } from "../../api/client";

/**
 * 028: the looks one may name, per type — what the visual packs hold (Portalab's own packs first, then the
 * live ones), read from the server: none is written in the interface's code. The pickers offer them, the
 * shop's editor sells them; read again when the packs change (``visuals.changed``).
 */
export interface LookVocabulary {
  epoch: number;
  looks: Record<string, string[]>;
  /** the socle's: free for everyone */
  free: Record<string, string[]>;
  /** whose pack is off: their owners keep them, « currently unavailable » */
  held: Record<string, string[]>;
}

export const LOOKS_KEY = ["visuals", "looks"] as const;

export function useLooks(enabled = true) {
  return useQuery({
    queryKey: LOOKS_KEY,
    enabled,
    staleTime: 60_000,
    queryFn: async () => (await api.GET("/api/v1/visuals/looks")).data as LookVocabulary,
  });
}

/** The looks of ``type`` (empty while the vocabulary is read). */
export function looksOf(vocabulary: LookVocabulary | undefined, type: string): string[] {
  return vocabulary?.looks?.[type] ?? [];
}
