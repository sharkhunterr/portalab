/**
 * The player's remembered choices (027, #2) — this browser's conveniences, like Plex's own player settings:
 * quality, subtitle size, burning, audio boost, volume and speed. Storage may be unavailable (private
 * windows): the defaults then apply.
 */
export interface PlayerPrefs {
  quality: string;
  subtitleSize: number; // percent
  burn: boolean;
  boost: number; // percent, 100 = none
  volume: number; // 0..1
  muted: boolean;
  rate: number;
  autoplayNext: boolean;
  subtitleLanguage: string | null; // the last language chosen, picked again on the next title
}

const KEY = "portalab.player";
export const DEFAULT_PREFS: PlayerPrefs = {
  quality: "original",
  subtitleSize: 100,
  burn: false,
  boost: 100,
  volume: 1,
  muted: false,
  rate: 1,
  autoplayNext: true,
  subtitleLanguage: null,
};

export function loadPrefs(): PlayerPrefs {
  try {
    const raw = globalThis.localStorage?.getItem(KEY);
    if (!raw) return { ...DEFAULT_PREFS };
    const stored = JSON.parse(raw) as Partial<PlayerPrefs>;
    return { ...DEFAULT_PREFS, ...stored };
  } catch {
    return { ...DEFAULT_PREFS };
  }
}

export function savePrefs(prefs: PlayerPrefs): void {
  try {
    globalThis.localStorage?.setItem(KEY, JSON.stringify(prefs));
  } catch {
    // storage refused: the choice lasts for this page only
  }
}
