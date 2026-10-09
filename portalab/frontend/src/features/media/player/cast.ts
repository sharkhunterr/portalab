import { useCallback, useEffect, useRef, useState } from "react";

/**
 * Chromecast and AirPlay for the portal's player (027, #11).
 *
 * * **Chromecast** — Google's Cast SDK (Chrome and Edge only), loaded when a player opens, with Google's
 *   default media receiver. The TV fetches the stream itself from the portal's *remote* playlist (a
 *   short-lived ticket for that one stream, no session); the player's controls drive it.
 * * **AirPlay** — Safari's own picker; Safari plays the remote playlist natively, so the Apple TV can
 *   fetch it too.
 */

// --- the few parts of the Cast SDK used here ---------------------------------------------------------
interface CastDevice {
  friendlyName: string;
}
interface CastSession {
  getCastDevice(): CastDevice;
  loadMedia(request: unknown): Promise<unknown>;
}
interface CastContext {
  setOptions(options: Record<string, unknown>): void;
  getCastState(): string;
  getCurrentSession(): CastSession | null;
  requestSession(): Promise<unknown>;
  endCurrentSession(stop: boolean): void;
  addEventListener(
    type: string,
    handler: (event: { sessionState?: string; castState?: string }) => void,
  ): void;
  removeEventListener(
    type: string,
    handler: (event: { sessionState?: string; castState?: string }) => void,
  ): void;
}
interface RemotePlayer {
  isConnected: boolean;
  isPaused: boolean;
  currentTime: number;
  duration: number;
  volumeLevel: number;
  isMuted: boolean;
  playerState: string | null;
}
interface RemotePlayerController {
  playOrPause(): void;
  seek(): void;
  setVolumeLevel(): void;
  muteOrUnmute(): void;
  stop(): void;
  addEventListener(type: string, handler: () => void): void;
  removeEventListener(type: string, handler: () => void): void;
}
interface CastFramework {
  CastContext: { getInstance(): CastContext };
  CastContextEventType: { CAST_STATE_CHANGED: string; SESSION_STATE_CHANGED: string };
  CastState: { NO_DEVICES_AVAILABLE: string };
  SessionState: { SESSION_STARTED: string; SESSION_RESUMED: string; SESSION_ENDED: string };
  RemotePlayer: new () => RemotePlayer;
  RemotePlayerController: new (player: RemotePlayer) => RemotePlayerController;
  RemotePlayerEventType: { ANY_CHANGE: string };
}
interface ChromeCast {
  media: {
    DEFAULT_MEDIA_RECEIVER_APP_ID: string;
    MediaInfo: new (url: string, contentType: string) => Record<string, unknown>;
    MovieMetadata: new () => Record<string, unknown>;
    LoadRequest: new (info: Record<string, unknown>) => Record<string, unknown>;
    StreamType: { BUFFERED: string };
    HlsSegmentFormat?: { TS: string };
  };
  AutoJoinPolicy: { ORIGIN_SCOPED: string };
}
type CastWindow = Window & {
  __onGCastApiAvailable?: (available: boolean) => void;
  cast?: { framework: CastFramework };
  chrome?: { cast?: ChromeCast };
};

const SDK = "https://www.gstatic.com/cv/js/sender/v1/cast_sender.js?loadCastFramework=1";
let loading: Promise<boolean> | null = null;

/** Loads the Cast SDK once (Chromium browsers only: elsewhere there is no cast button). */
export function loadCastSdk(): Promise<boolean> {
  if (loading) return loading;
  const w = window as CastWindow;
  loading = new Promise((resolve) => {
    const chromium = /Chrome\//.test(navigator.userAgent) && !/Firefox\//.test(navigator.userAgent);
    if (!chromium || !document.head) {
      resolve(false);
      return;
    }
    w.__onGCastApiAvailable = (available) => {
      const framework = w.cast?.framework;
      const chromeCast = w.chrome?.cast;
      if (available && framework && chromeCast) {
        framework.CastContext.getInstance().setOptions({
          receiverApplicationId: chromeCast.media.DEFAULT_MEDIA_RECEIVER_APP_ID,
          autoJoinPolicy: chromeCast.AutoJoinPolicy.ORIGIN_SCOPED,
        });
      }
      resolve(Boolean(available && framework && chromeCast));
    };
    const script = document.createElement("script");
    script.src = SDK;
    script.async = true;
    script.onerror = () => resolve(false);
    document.head.appendChild(script);
  });
  return loading;
}

export interface CastState {
  available: boolean; // a Cast device is around
  connected: boolean;
  device: string | null;
  time: number;
  duration: number;
  paused: boolean;
  volume: number;
  muted: boolean;
  idle: boolean; // the receiver finished (or has nothing loaded)
}

const IDLE: CastState = {
  available: false,
  connected: false,
  device: null,
  time: 0,
  duration: 0,
  paused: true,
  volume: 1,
  muted: false,
  idle: true,
};

export interface CastMedia {
  url: string; // absolute: the device fetches it
  title: string;
  subtitle?: string;
  startAt: number;
}

export function useCast() {
  const [state, setState] = useState<CastState>(IDLE);
  const parts = useRef<{
    framework: CastFramework;
    chrome: ChromeCast;
    player: RemotePlayer;
    controller: RemotePlayerController;
  } | null>(null);

  useEffect(() => {
    let alive = true;
    let cleanup: () => void = () => undefined;
    void loadCastSdk().then((ready) => {
      const w = window as CastWindow;
      const framework = w.cast?.framework;
      const chromeCast = w.chrome?.cast;
      if (!ready || !alive || !framework || !chromeCast) return;
      const context = framework.CastContext.getInstance();
      const player = new framework.RemotePlayer();
      const controller = new framework.RemotePlayerController(player);
      parts.current = { framework, chrome: chromeCast, player, controller };
      const sync = () =>
        setState((current) => ({
          ...current,
          available: context.getCastState() !== framework.CastState.NO_DEVICES_AVAILABLE,
          connected: player.isConnected,
          device: context.getCurrentSession()?.getCastDevice().friendlyName ?? null,
          time: player.currentTime,
          duration: player.duration,
          paused: player.isPaused,
          volume: player.volumeLevel,
          muted: player.isMuted,
          idle: !player.playerState || player.playerState === "IDLE",
        }));
      context.addEventListener(framework.CastContextEventType.CAST_STATE_CHANGED, sync);
      context.addEventListener(framework.CastContextEventType.SESSION_STATE_CHANGED, sync);
      controller.addEventListener(framework.RemotePlayerEventType.ANY_CHANGE, sync);
      sync();
      cleanup = () => {
        context.removeEventListener(framework.CastContextEventType.CAST_STATE_CHANGED, sync);
        context.removeEventListener(framework.CastContextEventType.SESSION_STATE_CHANGED, sync);
        controller.removeEventListener(framework.RemotePlayerEventType.ANY_CHANGE, sync);
      };
    });
    return () => {
      alive = false;
      cleanup();
    };
  }, []);

  const request = useCallback(() => {
    const p = parts.current;
    if (p)
      void p.framework.CastContext.getInstance()
        .requestSession()
        .catch(() => undefined);
  }, []);
  const end = useCallback(() => {
    parts.current?.framework.CastContext.getInstance().endCurrentSession(true);
  }, []);
  const load = useCallback(async (media: CastMedia) => {
    const p = parts.current;
    const session = p?.framework.CastContext.getInstance().getCurrentSession();
    if (!p || !session) return;
    const info = new p.chrome.media.MediaInfo(media.url, "application/x-mpegURL");
    info.streamType = p.chrome.media.StreamType.BUFFERED;
    if (p.chrome.media.HlsSegmentFormat) info.hlsSegmentFormat = p.chrome.media.HlsSegmentFormat.TS;
    const metadata = new p.chrome.media.MovieMetadata();
    metadata.title = media.title;
    if (media.subtitle) metadata.subtitle = media.subtitle;
    info.metadata = metadata;
    const request = new p.chrome.media.LoadRequest(info);
    request.currentTime = media.startAt;
    request.autoplay = true;
    await session.loadMedia(request);
  }, []);
  const playOrPause = useCallback(() => parts.current?.controller.playOrPause(), []);
  const seek = useCallback((to: number) => {
    const p = parts.current;
    if (!p) return;
    p.player.currentTime = to;
    p.controller.seek();
  }, []);
  const setVolume = useCallback((volume: number) => {
    const p = parts.current;
    if (!p) return;
    p.player.volumeLevel = volume;
    p.controller.setVolumeLevel();
  }, []);
  const toggleMute = useCallback(() => parts.current?.controller.muteOrUnmute(), []);

  return { state, request, end, load, playOrPause, seek, setVolume, toggleMute };
}

// --- AirPlay (Safari) -------------------------------------------------------------------------------
type AirPlayVideo = HTMLVideoElement & {
  webkitShowPlaybackTargetPicker?: () => void;
  webkitCurrentPlaybackTargetIsWireless?: boolean;
};

/** Safari plays HLS itself — the way to AirPlay (the Apple TV then fetches the stream directly). */
export function airPlayCapable(): boolean {
  return typeof window !== "undefined" && "WebKitPlaybackTargetAvailabilityEvent" in window;
}

export function useAirPlay(video: HTMLVideoElement | null) {
  const [available, setAvailable] = useState(false);
  const [wireless, setWireless] = useState(false);
  useEffect(() => {
    if (!video || !airPlayCapable()) return;
    const target = video as AirPlayVideo;
    const onAvailability = (event: Event) =>
      setAvailable((event as Event & { availability?: string }).availability === "available");
    const onWireless = () => setWireless(Boolean(target.webkitCurrentPlaybackTargetIsWireless));
    video.addEventListener("webkitplaybacktargetavailabilitychanged", onAvailability);
    video.addEventListener("webkitcurrentplaybacktargetiswirelesschanged", onWireless);
    return () => {
      video.removeEventListener("webkitplaybacktargetavailabilitychanged", onAvailability);
      video.removeEventListener("webkitcurrentplaybacktargetiswirelesschanged", onWireless);
    };
  }, [video]);
  const pick = useCallback(() => (video as AirPlayVideo | null)?.webkitShowPlaybackTargetPicker?.(), [video]);
  return { available, wireless, pick };
}
