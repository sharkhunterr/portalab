import type { PlayerTrack, PlayerVersion } from "./api";

/** Plex's qualities (027, #2): the cap in kbps and the height they convert to. */
export const QUALITY_INFO: Record<string, { kbps: number; height: number } | null> = {
  original: null,
  "20m": { kbps: 20_000, height: 1080 },
  "12m": { kbps: 12_000, height: 1080 },
  "10m": { kbps: 10_000, height: 1080 },
  "8m": { kbps: 8_000, height: 1080 },
  "4m": { kbps: 4_000, height: 720 },
  "3m": { kbps: 3_000, height: 720 },
  "2m": { kbps: 2_000, height: 720 },
  "1500k": { kbps: 1_500, height: 480 },
  "720k": { kbps: 720, height: 360 },
  "320k": { kbps: 320, height: 240 },
};

/** The qualities worth offering for a file: « original », then only those below its own bitrate. */
export function qualitiesFor(allowed: string[], version: PlayerVersion | undefined): string[] {
  const source = version?.bitrate_kbps ?? null;
  return allowed.filter((key) => {
    const info = QUALITY_INFO[key];
    if (info === undefined) return false;
    return info === null || source === null || info.kbps < source;
  });
}

export function bitrateLabel(kbps: number): string {
  return kbps >= 1000 ? `${Number((kbps / 1000).toFixed(1))} Mb/s` : `${kbps} kb/s`;
}

/** The subtitle to start with: the one the member chose on the service, else their last language's. */
export function initialSubtitle(version: PlayerVersion | undefined, language: string | null): string | null {
  const tracks = version?.subtitles ?? [];
  const selected = tracks.find((t) => t.selected);
  if (selected) return selected.id;
  if (!language) return null;
  return tracks.find((t) => t.language === language && !t.forced)?.id ?? null;
}

export function initialAudio(version: PlayerVersion | undefined): string | null {
  const tracks = version?.audio ?? [];
  return (tracks.find((t) => t.selected) ?? tracks.find((t) => t.default) ?? tracks[0])?.id ?? null;
}

export function trackById(tracks: PlayerTrack[] | undefined, id: string | null): PlayerTrack | undefined {
  return id ? tracks?.find((t) => t.id === id) : undefined;
}

/** « 1:02:03 » or « 4:05 ». */
export function clock(seconds: number): string {
  const total = Math.max(0, Math.floor(Number.isFinite(seconds) ? seconds : 0));
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = String(total % 60).padStart(2, "0");
  return h > 0 ? `${h}:${String(m).padStart(2, "0")}:${s}` : `${m}:${s}`;
}
