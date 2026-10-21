import { useSyncExternalStore } from "react";
import { toggle as toggleBook, useListen } from "../listen/store";

/**
 * Issue 168: the radio of the whole portal — one audio element, kept while browsing. A live stream: each
 * start opens a fresh connection (no stale buffer), a stop closes it.
 */
export const RADIO_STREAM = "/api/v1/media/radio/stream";

export interface RadioPlayback {
  playing: boolean;
  loading: boolean;
  failed: boolean;
  volume: number;
}

let state: RadioPlayback = { playing: false, loading: false, failed: false, volume: 0.8 };
const listeners = new Set<() => void>();
let audio: HTMLAudioElement | null = null;

function set(next: Partial<RadioPlayback>) {
  state = { ...state, ...next };
  for (const listener of listeners) listener();
}

function element(): HTMLAudioElement {
  if (audio) return audio;
  audio = new Audio();
  audio.preload = "none";
  audio.volume = state.volume;
  audio.addEventListener("playing", () => set({ playing: true, loading: false, failed: false }));
  audio.addEventListener("waiting", () => set({ loading: true }));
  audio.addEventListener("error", () => {
    if (audio?.getAttribute("src")) set({ playing: false, loading: false, failed: true });
  });
  return audio;
}

export function useRadioPlayback(): RadioPlayback {
  return useSyncExternalStore(
    (listener) => {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
    () => state,
    () => state,
  );
}

export function playRadio(bookPlaying = false) {
  if (bookPlaying) toggleBook(); // an audiobook steps aside
  const player = element();
  player.src = `${RADIO_STREAM}?t=${Date.now()}`;
  set({ loading: true, failed: false });
  player.play().catch(() => set({ playing: false, loading: false, failed: true }));
}

export function stopRadio() {
  if (!audio) return;
  audio.pause();
  audio.removeAttribute("src");
  audio.load(); // closes the connection
  set({ playing: false, loading: false });
}

export function setRadioVolume(volume: number) {
  const value = Math.min(1, Math.max(0, volume));
  if (audio) audio.volume = value;
  set({ volume: value });
}

/** Play or stop, an audiobook stepping aside when the radio starts. */
export function useRadioToggle(): () => void {
  const playback = useRadioPlayback();
  const book = useListen();
  return () => (playback.playing || playback.loading ? stopRadio() : playRadio(book.playing));
}
