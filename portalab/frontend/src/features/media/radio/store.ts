import { useSyncExternalStore } from "react";
import { closeBook, useListen } from "../listen/store";

/**
 * Issue 168: the radio of the whole portal — one audio element, kept while browsing, in the portal's audio
 * player (the bar at the bottom and its bigger view, like an audiobook's — music will share it). A live
 * stream: each start opens a fresh connection (no stale buffer), a pause closes it.
 */
export const RADIO_STREAM = "/api/v1/media/radio/stream";

export interface RadioPlayback {
  /** the player is shown (the bar at the bottom), playing or paused */
  open: boolean;
  /** its bigger view */
  expanded: boolean;
  playing: boolean;
  loading: boolean;
  failed: boolean;
  volume: number;
}

let state: RadioPlayback = {
  open: false,
  expanded: false,
  playing: false,
  loading: false,
  failed: false,
  volume: 0.8,
};
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

export function playRadio(bookOpen = false) {
  if (bookOpen) closeBook(); // one player at a time: the audiobook keeps its place and steps aside
  const player = element();
  player.src = `${RADIO_STREAM}?t=${Date.now()}`;
  set({ open: true, loading: true, failed: false });
  player.play().catch(() => set({ playing: false, loading: false, failed: true }));
}

export function stopRadio() {
  if (!audio) return;
  audio.pause();
  audio.removeAttribute("src");
  audio.load(); // closes the connection
  set({ playing: false, loading: false });
}

/** Open the player's bigger view (opening the player if needed, without playing). */
export function expandRadio(expanded = true) {
  set({ open: state.open || expanded, expanded });
}

/** Close the player: the stream stops, the bar goes. */
export function closeRadio() {
  stopRadio();
  set({ open: false, expanded: false });
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
  return () => (playback.playing || playback.loading ? stopRadio() : playRadio(Boolean(book.objectId)));
}
