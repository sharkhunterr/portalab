import { useSyncExternalStore } from "react";
import { ApiError } from "../../../state/regions";
import { imageUrl } from "../api";
import {
  type AudioChapter,
  audioUrl,
  fetchListen,
  type ListenInfo,
  reportListening,
  type SessionState,
} from "../books/api";

/**
 * #20: the portal's audiobook player — one audio element for the whole portal, so listening carries on while
 * the member browses. An audiobook made of several files plays them one after the other as one whole: every
 * position here is in the whole book. Where the member is goes back to the portal (and the library) every
 * twenty seconds, at a pause, at the end, and when the page goes away. The lock screen and headphones drive it
 * through the Media Session.
 */
export interface ListenState {
  objectId: string | null;
  title: string;
  image: string | null;
  info: ListenInfo | null;
  status: "idle" | "loading" | "ready" | "error";
  error: string | null;
  playing: boolean;
  buffering: boolean;
  position: number; // in the whole book, seconds
  duration: number;
  rate: number;
  sleep: { until: number } | { chapterEnd: number } | null;
  expanded: boolean;
}

export const RATES = [0.5, 0.75, 0.9, 1, 1.1, 1.25, 1.5, 1.75, 2, 2.5, 3] as const;
export const SKIP_S = 30;
const SAVED = "portalab.listen";
const REPORT_MS = 20_000;

const initial: ListenState = {
  objectId: null,
  title: "",
  image: null,
  info: null,
  status: "idle",
  error: null,
  playing: false,
  buffering: false,
  position: 0,
  duration: 0,
  rate: 1,
  sleep: null,
  expanded: false,
};

let state: ListenState = initial;
const listeners = new Set<() => void>();
let audio: HTMLAudioElement | null = null;
let track: number | null = null; // the file playing, for a book made of several
let seq = 0;
let lastReport = 0;
let pendingSeek: number | null = null;
let autoplayAfterLoad = false;

function set(patch: Partial<ListenState>) {
  state = { ...state, ...patch };
  for (const listener of listeners) listener();
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function useListen(): ListenState {
  return useSyncExternalStore(
    subscribe,
    () => state,
    () => initial,
  );
}

function remember() {
  try {
    if (state.objectId) {
      localStorage.setItem(
        SAVED,
        JSON.stringify({
          objectId: state.objectId,
          title: state.title,
          image: state.image,
          rate: state.rate,
        }),
      );
    } else {
      localStorage.removeItem(SAVED);
    }
  } catch {
    // private window: the player simply does not come back after a reload
  }
}

// --- the files of the book ----------------------------------------------------------------------------
function tracks() {
  return state.info?.item.tracks ?? [];
}

/** Which file holds a position in the whole book, and where in it. */
function locate(position: number): { track: number | null; offset: number } {
  const files = tracks();
  if (!files.length) return { track: null, offset: position };
  let found = files[0];
  for (const file of files) if (file && position >= file.start_s) found = file;
  return found
    ? { track: found.index, offset: Math.max(0, position - found.start_s) }
    : { track: null, offset: 0 };
}

function startOf(index: number | null): number {
  if (index === null) return 0;
  return tracks().find((t) => t.index === index)?.start_s ?? 0;
}

function element(): HTMLAudioElement {
  if (audio) return audio;
  const created = new Audio();
  created.preload = "metadata";
  created.addEventListener("timeupdate", onTime);
  created.addEventListener("play", () => {
    set({ playing: true });
    report("playing", true);
  });
  created.addEventListener("pause", () => {
    set({ playing: false });
    if (!created.ended) report("paused", true);
  });
  created.addEventListener("waiting", () => set({ buffering: true }));
  created.addEventListener("playing", () => set({ buffering: false }));
  created.addEventListener("canplay", () => set({ buffering: false }));
  created.addEventListener("loadedmetadata", () => {
    if (pendingSeek !== null) {
      created.currentTime = pendingSeek;
      pendingSeek = null;
    }
    created.playbackRate = state.rate;
    if (autoplayAfterLoad) {
      autoplayAfterLoad = false;
      void created.play().catch(() => set({ playing: false }));
    }
  });
  created.addEventListener("ended", onEnded);
  created.addEventListener("error", () => {
    if (state.objectId) set({ status: "error", error: "unavailable", playing: false, buffering: false });
  });
  audio = created;
  return created;
}

function load(index: number | null, offset: number, play: boolean) {
  const info = state.info;
  if (!info) return;
  const media = element();
  track = index;
  pendingSeek = offset;
  autoplayAfterLoad = play;
  media.src = audioUrl(info.ticket, index);
  media.load();
}

function onTime() {
  const media = element();
  const position = startOf(track) + media.currentTime;
  set({ position });
  const sleep = state.sleep;
  if (sleep && "until" in sleep && Date.now() >= sleep.until) {
    set({ sleep: null });
    media.pause();
  } else if (sleep && "chapterEnd" in sleep && position >= sleep.chapterEnd) {
    set({ sleep: null });
    media.pause();
  }
  if (state.playing && Date.now() - lastReport >= REPORT_MS) report("playing");
  updatePositionState();
}

function onEnded() {
  const files = tracks();
  const index = files.findIndex((t) => t.index === track);
  const next = index >= 0 ? files[index + 1] : undefined;
  if (next) {
    load(next.index, 0, true);
    return;
  }
  set({ playing: false, position: state.duration });
  report("finished", true);
}

function report(kind: SessionState, force = false) {
  const info = state.info;
  if (!info || (!force && Date.now() - lastReport < REPORT_MS)) return;
  lastReport = Date.now();
  seq += 1;
  void reportListening(info.ticket, kind, state.position, state.duration || null, track, seq).catch(() => {
    // the next report says it again
  });
}

// --- what the member does ------------------------------------------------------------------------------
export async function openBook(
  objectId: string,
  options: { title?: string; image?: string | null; play?: boolean; at?: number } = {},
): Promise<void> {
  const play = options.play ?? true;
  if (state.objectId === objectId && state.info && state.status === "ready") {
    if (options.at !== undefined) seekTo(options.at);
    if (play)
      element()
        .play()
        .catch(() => undefined);
    return;
  }
  if (state.objectId) closeBook();
  seq = 0;
  lastReport = 0;
  set({
    objectId,
    title: options.title ?? "",
    image: options.image ?? null,
    info: null,
    status: "loading",
    error: null,
    position: 0,
    duration: 0,
    sleep: null,
  });
  remember();
  try {
    const info = await fetchListen(objectId);
    if (state.objectId !== objectId) return; // another book was opened meanwhile
    const duration = info.item.duration_s ?? 0;
    let from = options.at ?? info.resume?.position_s ?? 0;
    if (duration && from >= duration - 15) from = 0; // finished: from the start again
    set({ info, status: "ready", duration, position: from, title: options.title || info.item.title });
    remember();
    const where = locate(from);
    load(where.track, where.offset, play);
    mediaSession();
  } catch (error) {
    set({
      status: "error",
      error: error instanceof ApiError ? (error.code ?? "unavailable") : "unavailable",
    });
  }
}

export function toggle() {
  const media = element();
  if (!state.info) return;
  if (media.paused) void media.play().catch(() => undefined);
  else media.pause();
}

export function seekTo(position: number) {
  if (!state.info) return;
  const target = Math.min(Math.max(0, position), state.duration || position);
  const where = locate(target);
  set({ position: target });
  if (where.track !== track) {
    load(where.track, where.offset, !element().paused);
  } else {
    element().currentTime = where.offset;
  }
  report(element().paused ? "paused" : "playing", true);
}

export function skip(seconds: number) {
  seekTo(state.position + seconds);
}

export function setRate(rate: number) {
  set({ rate });
  element().playbackRate = rate;
  remember();
}

export function chapters(): AudioChapter[] {
  return state.info?.item.chapters ?? [];
}

export function currentChapter(position = state.position): AudioChapter | null {
  let found: AudioChapter | null = null;
  for (const chapter of chapters()) if (position >= chapter.start_s - 0.5) found = chapter;
  return found;
}

export function chapterStep(step: 1 | -1) {
  const list = chapters();
  const here = currentChapter();
  const index = here ? list.indexOf(here) : -1;
  if (step < 0 && here && state.position - here.start_s > 5) {
    seekTo(here.start_s); // the start of this chapter first
    return;
  }
  const next = list[index + step];
  if (next) seekTo(next.start_s);
}

/** Pause after ``minutes``, at the end of the chapter (``"chapter"``), or never again (``null``). */
export function setSleep(choice: number | "chapter" | null) {
  if (choice === null) set({ sleep: null });
  else if (choice === "chapter") {
    const here = currentChapter();
    set({ sleep: here ? { chapterEnd: here.end_s } : null });
  } else set({ sleep: { until: Date.now() + choice * 60_000 } });
}

export function setExpanded(expanded: boolean) {
  set({ expanded });
}

export function closeBook() {
  const media = audio;
  if (state.info && media) {
    if (!media.paused) media.pause();
    report("stopped", true);
  }
  if (media) {
    media.removeAttribute("src");
    media.load();
  }
  track = null;
  set({ ...initial, rate: state.rate });
  remember();
  if ("mediaSession" in navigator) navigator.mediaSession.metadata = null;
}

/** After a reload, the last audiobook comes back paused where the member left it. */
export function restore() {
  if (state.objectId) return;
  try {
    const saved = JSON.parse(localStorage.getItem(SAVED) ?? "null") as {
      objectId?: string;
      title?: string;
      image?: string | null;
      rate?: number;
    } | null;
    if (saved?.rate) set({ rate: saved.rate });
    if (saved?.objectId) {
      void openBook(saved.objectId, {
        title: saved.title ?? "",
        image: saved.image ?? null,
        play: false,
      });
    }
  } catch {
    // nothing to restore
  }
}

/** The page goes away: the last position is sent (keepalive). */
export function leaving() {
  if (state.info && audio && !audio.paused) report("paused", true);
}

// --- the lock screen and headphones -------------------------------------------------------------------
function mediaSession() {
  if (!("mediaSession" in navigator) || !state.info) return;
  const session = navigator.mediaSession;
  const cover = imageUrl(state.image);
  session.metadata = new MediaMetadata({
    title: state.title || state.info.item.title,
    artist: state.info.item.author ?? "",
    album: state.info.item.narrator ?? "",
    ...(cover ? { artwork: [{ src: new URL(cover, window.location.href).href }] } : {}),
  });
  const handle = (action: MediaSessionAction, fn: MediaSessionActionHandler) => {
    try {
      session.setActionHandler(action, fn);
    } catch {
      // an action this browser does not offer
    }
  };
  handle(
    "play",
    () =>
      void element()
        .play()
        .catch(() => undefined),
  );
  handle("pause", () => element().pause());
  handle("seekbackward", (details) => skip(-(details.seekOffset ?? SKIP_S)));
  handle("seekforward", (details) => skip(details.seekOffset ?? SKIP_S));
  handle("seekto", (details) => {
    if (details.seekTime !== undefined) seekTo(details.seekTime);
  });
  handle("previoustrack", () => chapterStep(-1));
  handle("nexttrack", () => chapterStep(1));
  handle("stop", () => closeBook());
}

function updatePositionState() {
  if (!("mediaSession" in navigator) || !state.duration) return;
  try {
    navigator.mediaSession.setPositionState({
      duration: state.duration,
      position: Math.min(state.position, state.duration),
      playbackRate: state.rate,
    });
  } catch {
    // an inconsistent moment (loading a file): the next update fixes it
  }
}
