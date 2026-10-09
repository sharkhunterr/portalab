import Hls from "hls.js";
import {
  type CSSProperties,
  type KeyboardEvent as ReactKeyboardEvent,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { Icon } from "../../../design-system/components/Icon";
import { useT } from "../../../i18n/hooks/useT";
import { ApiError } from "../../../state/regions";
import {
  type Cue,
  fetchCues,
  type PlaybackState,
  type PlayerInfo,
  playerImage,
  reportTimeline,
  type StreamStarted,
  startStream,
  stopStream,
  streamUrl,
} from "./api";
import { loadPrefs, type PlayerPrefs, savePrefs } from "./prefs";
import { clock, initialAudio, initialSubtitle, qualitiesFor, trackById } from "./quality";
import { SettingsMenu } from "./SettingsMenu";
import "./player.css";

/**
 * The portal's video player (027, #2): the media server's HLS stream (direct or transcoded, as Plex
 * decides) played with hls.js, with Plex's settings — quality, version, audio, subtitles (drawn here, or
 * burnt in), subtitle size, audio boost — plus speed, chapters, « skip intro », next episode, resume,
 * picture-in-picture and keyboard shortcuts. Its look follows the theme's tokens.
 */
export interface VideoPlayerProps {
  objectId: string;
  info: PlayerInfo;
  onExit: () => void;
  onEpisode: (item: string) => void;
}

const HIDE_AFTER_MS = 3000;
const REPORT_EVERY_MS = 10_000;
const CUES_EVERY_MS = 2500;
const NEXT_COUNTDOWN_S = 10;

function cueKey(cue: Cue): string {
  return `${cue.start_s}|${cue.end_s}|${cue.text}`;
}

function mergeCues(previous: Cue[], incoming: Cue[]): Cue[] {
  if (!incoming.length) return previous;
  const all = new Map(previous.map((c) => [cueKey(c), c]));
  for (const cue of incoming) all.set(cueKey(cue), cue);
  return [...all.values()].sort((a, b) => a.start_s - b.start_s).slice(-4000);
}

export function VideoPlayer({ objectId, info, onExit, onEpisode }: VideoPlayerProps) {
  const t = useT();
  const item = info.item;
  const duration = item.duration_s ?? null;
  const [prefs, setPrefsState] = useState<PlayerPrefs>(loadPrefs);
  const updatePrefs = useCallback((patch: Partial<PlayerPrefs>) => {
    setPrefsState((current) => {
      const next = { ...current, ...patch };
      savePrefs(next);
      return next;
    });
  }, []);

  // --- what plays ---------------------------------------------------------------------------------------
  const [versionIndex, setVersionIndex] = useState(0);
  const version = item.versions[versionIndex] ?? item.versions[0];
  const [audio, setAudio] = useState<string | null>(() => initialAudio(item.versions[0]));
  const [subtitle, setSubtitle] = useState<string | null>(() =>
    initialSubtitle(item.versions[0], prefs.subtitleLanguage),
  );
  const qualities = useMemo(() => qualitiesFor(info.qualities, version), [info.qualities, version]);
  const quality = qualities.includes(prefs.quality) ? prefs.quality : (qualities[0] ?? "original");
  const resumable = item.resume_s > 30 && (!duration || item.resume_s < duration * 0.95);
  const [startAt, setStartAt] = useState<number | null>(resumable ? null : 0); // null: asking

  // --- the stream ---------------------------------------------------------------------------------------
  const frameRef = useRef<HTMLElement>(null);
  const videoRef = useRef<HTMLVideoElement>(null);
  const positionRef = useRef(0);
  const firstRef = useRef(true);
  const streamRef = useRef<StreamStarted | null>(null);
  const tRef = useRef(t);
  tRef.current = t;
  const [stream, setStream] = useState<StreamStarted | null>(null);
  const [failure, setFailure] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);
  const burntSize = prefs.burn ? prefs.subtitleSize : 100;

  useEffect(() => {
    const video = videoRef.current;
    if (startAt === null || !video) return;
    // ``attempt`` restarts the same stream after a failure
    void attempt;
    let cancelled = false;
    let hls: Hls | null = null;
    let ticket: string | null = null;
    const from = firstRef.current ? startAt : positionRef.current;
    firstRef.current = false;
    setFailure(null);
    startStream(objectId, {
      item: item.external_id,
      version: versionIndex,
      quality,
      audio,
      subtitle,
      burn: prefs.burn,
      subtitle_size: burntSize,
      boost: prefs.boost,
      duration_s: duration,
    })
      .then((started) => {
        if (cancelled) {
          void stopStream(started.ticket);
          return;
        }
        ticket = started.ticket;
        streamRef.current = started;
        setStream(started);
        const url = streamUrl(started);
        if (Hls.isSupported()) {
          hls = new Hls({
            enableWorker: false,
            startPosition: from,
            // a short buffer first: the picture shows sooner (Plex's segments are 10 s, several MB each)
            maxBufferLength: 30,
            maxMaxBufferLength: 90,
            backBufferLength: 60,
          });
          hls.on(Hls.Events.ERROR, (_event, data) => {
            if (!data.fatal) return;
            if (data.type === Hls.ErrorTypes.MEDIA_ERROR) {
              hls?.recoverMediaError();
              return;
            }
            setFailure(tRef.current("media:player.error.stream"));
          });
          hls.on(Hls.Events.MANIFEST_PARSED, () => {
            video.play().catch(() => undefined);
          });
          hls.loadSource(url);
          hls.attachMedia(video);
        } else if (video.canPlayType("application/vnd.apple.mpegurl")) {
          video.src = url; // Safari plays HLS itself
          video.addEventListener(
            "loadedmetadata",
            () => {
              video.currentTime = from;
              video.play().catch(() => undefined);
            },
            { once: true },
          );
        } else {
          setFailure(tRef.current("media:player.error.browser"));
        }
      })
      .catch((error: unknown) => {
        if (cancelled) return;
        const code = error instanceof ApiError ? error.code : undefined;
        setFailure(
          tRef.current(
            code === "media.player_denied"
              ? "media:player.error.denied"
              : code === "media.player_unlinked"
                ? "media:player.error.unlinked"
                : "media:player.error.start",
          ),
        );
      });
    return () => {
      cancelled = true;
      hls?.destroy();
      video.removeAttribute("src");
      video.load();
      if (ticket) {
        void reportTimeline(ticket, "stopped", positionRef.current, duration);
        void stopStream(ticket);
      }
      streamRef.current = null;
      setStream(null);
    };
  }, [
    startAt,
    attempt,
    objectId,
    item.external_id,
    versionIndex,
    quality,
    audio,
    subtitle,
    prefs.burn,
    burntSize,
    prefs.boost,
    duration,
  ]);

  // --- the video's state --------------------------------------------------------------------------------
  const [paused, setPaused] = useState(true);
  const [waiting, setWaiting] = useState(false);
  const [time, setTime] = useState(0);
  const [buffered, setBuffered] = useState(0);
  const [ended, setEnded] = useState(false);
  const report = useCallback(
    (state?: PlaybackState) => {
      const video = videoRef.current;
      const current = streamRef.current;
      if (!video || !current) return;
      const now: PlaybackState = state ?? (video.paused ? "paused" : "playing");
      void reportTimeline(current.ticket, now, video.currentTime, duration).catch(() => undefined);
    },
    [duration],
  );

  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;
    video.volume = prefs.volume;
    video.muted = prefs.muted;
    video.playbackRate = prefs.rate;
  }, [prefs.volume, prefs.muted, prefs.rate]);

  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;
    const onTime = () => {
      positionRef.current = video.currentTime;
      setTime(video.currentTime);
      const ranges = video.buffered;
      for (let i = 0; i < ranges.length; i += 1) {
        if (ranges.start(i) <= video.currentTime + 0.5 && ranges.end(i) >= video.currentTime) {
          setBuffered(ranges.end(i));
        }
      }
    };
    const onPlay = () => {
      setPaused(false);
      setEnded(false);
      report("playing");
    };
    const onPause = () => {
      setPaused(true);
      report("paused");
    };
    const onWaiting = () => setWaiting(true);
    const onPlaying = () => setWaiting(false);
    const onEnded = () => {
      setEnded(true);
      report("stopped");
    };
    const onRate = () => {
      if (video.playbackRate !== prefs.rate) video.playbackRate = prefs.rate;
    };
    video.addEventListener("timeupdate", onTime);
    video.addEventListener("progress", onTime);
    video.addEventListener("play", onPlay);
    video.addEventListener("pause", onPause);
    video.addEventListener("waiting", onWaiting);
    video.addEventListener("playing", onPlaying);
    video.addEventListener("ended", onEnded);
    video.addEventListener("loadedmetadata", onRate);
    return () => {
      video.removeEventListener("timeupdate", onTime);
      video.removeEventListener("progress", onTime);
      video.removeEventListener("play", onPlay);
      video.removeEventListener("pause", onPause);
      video.removeEventListener("waiting", onWaiting);
      video.removeEventListener("playing", onPlaying);
      video.removeEventListener("ended", onEnded);
      video.removeEventListener("loadedmetadata", onRate);
    };
  }, [report, prefs.rate]);

  // where the member is, every few seconds and when the page goes away (resume point, activity)
  useEffect(() => {
    if (!stream) return;
    const timer = window.setInterval(() => report(), REPORT_EVERY_MS);
    const leave = () => {
      report("stopped");
      void stopStream(stream.ticket);
    };
    window.addEventListener("pagehide", leave);
    return () => {
      window.clearInterval(timer);
      window.removeEventListener("pagehide", leave);
    };
  }, [stream, report]);

  // --- text subtitles, drawn here -----------------------------------------------------------------------
  const [cues, setCues] = useState<Cue[]>([]);
  const textSubtitles = stream?.subtitles === "text";
  useEffect(() => {
    setCues([]);
    const video = videoRef.current;
    if (!stream || !textSubtitles || !video) return;
    let alive = true;
    const load = (seek: boolean) => {
      fetchCues(stream.ticket, video.currentTime, seek)
        .then((list) => {
          if (alive) setCues((previous) => mergeCues(previous, list));
        })
        .catch(() => undefined);
    };
    load(false);
    const timer = window.setInterval(() => load(false), CUES_EVERY_MS);
    const onSeeked = () => load(true);
    video.addEventListener("seeked", onSeeked);
    return () => {
      alive = false;
      window.clearInterval(timer);
      video.removeEventListener("seeked", onSeeked);
    };
  }, [stream, textSubtitles]);
  const showing = cues.filter((c) => c.start_s <= time && time < c.end_s);

  // --- controls -----------------------------------------------------------------------------------------
  const [active, setActive] = useState(true);
  const [menuOpen, setMenuOpen] = useState(false);
  const hideTimer = useRef<number | undefined>(undefined);
  const poke = useCallback(() => {
    setActive(true);
    window.clearTimeout(hideTimer.current);
    hideTimer.current = window.setTimeout(() => setActive(false), HIDE_AFTER_MS);
  }, []);
  useEffect(() => () => window.clearTimeout(hideTimer.current), []);
  const visible = active || paused || menuOpen || !stream || ended;

  const toggle = useCallback(() => {
    const video = videoRef.current;
    if (!video) return;
    if (video.paused) video.play().catch(() => undefined);
    else video.pause();
  }, []);
  const seek = useCallback(
    (to: number) => {
      const video = videoRef.current;
      if (!video) return;
      const limit = duration ?? video.duration;
      video.currentTime = Math.max(0, Number.isFinite(limit) ? Math.min(to, limit - 1) : to);
      poke();
    },
    [duration, poke],
  );
  const [fullscreen, setFullscreen] = useState(false);
  useEffect(() => {
    const onChange = () => setFullscreen(document.fullscreenElement === frameRef.current);
    document.addEventListener("fullscreenchange", onChange);
    return () => document.removeEventListener("fullscreenchange", onChange);
  }, []);
  const toggleFullscreen = useCallback(() => {
    if (document.fullscreenElement) void document.exitFullscreen().catch(() => undefined);
    else void frameRef.current?.requestFullscreen?.().catch(() => undefined);
  }, []);
  const pipSupported = typeof document !== "undefined" && "pictureInPictureEnabled" in document;
  const togglePip = () => {
    const video = videoRef.current;
    if (!video) return;
    if (document.pictureInPictureElement) void document.exitPictureInPicture().catch(() => undefined);
    else void video.requestPictureInPicture?.().catch(() => undefined);
  };
  const textTracks = version?.subtitles ?? [];
  const toggleSubtitles = useCallback(() => {
    if (subtitle) {
      setSubtitle(null);
      return;
    }
    const preferred =
      textTracks.find((s) => s.language === prefs.subtitleLanguage && !s.forced) ?? textTracks[0];
    if (preferred) setSubtitle(preferred.id);
  }, [subtitle, textTracks, prefs.subtitleLanguage]);

  // --- markers: intro, credits, next episode ------------------------------------------------------------
  const intro = item.markers.find((m) => m.kind === "intro" && time >= m.start_s && time < m.end_s - 1);
  const credits = item.markers.find((m) => m.kind === "credits" && time >= m.start_s && time < m.end_s - 1);
  const finalCredits = credits && (!duration || credits.end_s >= duration - 5);
  const [nextDismissed, setNextDismissed] = useState(false);
  const offerNext = Boolean(item.next_id) && !nextDismissed && (Boolean(finalCredits) || ended);
  const [countdown, setCountdown] = useState(NEXT_COUNTDOWN_S);
  useEffect(() => {
    if (!offerNext || !prefs.autoplayNext || paused) {
      setCountdown(NEXT_COUNTDOWN_S);
      return;
    }
    const timer = window.setInterval(() => setCountdown((c) => Math.max(0, c - 1)), 1000);
    return () => window.clearInterval(timer);
  }, [offerNext, prefs.autoplayNext, paused]);
  useEffect(() => {
    if (offerNext && prefs.autoplayNext && countdown === 0 && item.next_id) onEpisode(item.next_id);
  }, [offerNext, prefs.autoplayNext, countdown, item.next_id, onEpisode]);

  // --- keyboard -----------------------------------------------------------------------------------------
  const onKeyDown = (event: ReactKeyboardEvent<HTMLElement>) => {
    const target = event.target as HTMLElement;
    const inControl = target.closest("button, input, [role='dialog']") !== null;
    const video = videoRef.current;
    if (!video) return;
    const key = event.key;
    if ((key === " " || key === "k") && !inControl) toggle();
    else if ((key === "ArrowLeft" || key === "j") && !(inControl && target.tagName === "INPUT"))
      seek(video.currentTime - 10);
    else if ((key === "ArrowRight" || key === "l") && !(inControl && target.tagName === "INPUT"))
      seek(video.currentTime + 10);
    else if (key === "ArrowUp" && !inControl)
      updatePrefs({ volume: Math.min(1, prefs.volume + 0.1), muted: false });
    else if (key === "ArrowDown" && !inControl) updatePrefs({ volume: Math.max(0, prefs.volume - 0.1) });
    else if (key === "m") updatePrefs({ muted: !prefs.muted });
    else if (key === "f") toggleFullscreen();
    else if (key === "c") toggleSubtitles();
    else if (key === "Escape") {
      if (menuOpen) setMenuOpen(false);
      else if (!document.fullscreenElement) onExit();
      else return;
    } else return;
    event.preventDefault();
    poke();
  };

  const total = duration ?? (stream ? (videoRef.current?.duration ?? 0) : 0);
  const percent = total > 0 ? (time / total) * 100 : 0;
  const bufferedPercent = total > 0 ? Math.min(100, (buffered / total) * 100) : 0;
  const [hover, setHover] = useState<{ x: number; at: number } | null>(null);
  const subtitleTrack = trackById(textTracks, subtitle);
  // 027 (#13): the chapter under the pointer, its picture — or the server's preview of that moment
  const hoverChapter = hover
    ? item.chapters.find((c) => hover.at >= c.start_s && hover.at < c.end_s)
    : undefined;
  const hoverPicture =
    hover && stream
      ? version?.previews
        ? playerImage(stream.ticket, version.previews, Math.round(hover.at / 5) * 5)
        : hoverChapter?.image
          ? playerImage(stream.ticket, hoverChapter.image)
          : null
      : null;
  const title = item.parent_title ? `${item.parent_title} · ${item.label ?? ""} ${item.title}` : item.title;

  return (
    <section
      ref={frameRef}
      className="player"
      data-visible={visible}
      data-waiting={waiting && !paused}
      onPointerMove={poke}
      onKeyDown={onKeyDown}
      // biome-ignore lint/a11y/noNoninteractiveTabindex: focusable so the shortcuts work at once
      tabIndex={0}
      aria-label={t("media:player.label", { title })}
      style={{ "--player-subtitle-scale": prefs.subtitleSize / 100 } as CSSProperties}
    >
      {/* biome-ignore lint/a11y/useMediaCaption: subtitles are drawn by the player from the service's tracks */}
      <video
        ref={videoRef}
        className="player-video"
        playsInline
        onClick={() => {
          if (menuOpen) setMenuOpen(false);
          else toggle();
        }}
        onDoubleClick={toggleFullscreen}
      />

      {showing.length > 0 ? (
        <div className="player-subtitles" aria-live="off">
          {showing.map((cue) => (
            <p key={cueKey(cue)}>{cue.text}</p>
          ))}
        </div>
      ) : null}

      {waiting && !paused ? (
        <div className="player-spinner" role="status" aria-label={t("media:player.loading")} />
      ) : null}

      {startAt === null ? (
        <div className="player-resume" role="dialog" aria-label={t("media:player.resume.title")}>
          <p>{t("media:player.resume.title")}</p>
          <div>
            <button
              type="button"
              className="player-pill"
              data-primary
              onClick={() => setStartAt(item.resume_s)}
            >
              <Icon name="play" size={18} />
              {t("media:player.resume.from", { time: clock(item.resume_s) })}
            </button>
            <button type="button" className="player-pill" onClick={() => setStartAt(0)}>
              <Icon name="replay" size={18} />
              {t("media:player.resume.start")}
            </button>
          </div>
        </div>
      ) : null}

      {failure ? (
        <div className="player-failure" role="alert">
          <Icon name="alert" size={28} />
          <p>{failure}</p>
          <div>
            <button
              type="button"
              className="player-pill"
              data-primary
              onClick={() => setAttempt((n) => n + 1)}
            >
              <Icon name="sync" size={18} />
              {t("media:player.retry")}
            </button>
            <button type="button" className="player-pill" onClick={onExit}>
              {t("media:player.back")}
            </button>
          </div>
        </div>
      ) : null}

      <div className="player-top" aria-hidden={!visible}>
        <button type="button" className="player-icon" onClick={onExit} aria-label={t("media:player.back")}>
          <Icon name="back" size={22} />
        </button>
        <div className="player-title">
          <strong>{item.parent_title ?? item.title}</strong>
          {item.parent_title ? (
            <span>
              {item.label} · {item.title}
            </span>
          ) : item.year ? (
            <span>{item.year}</span>
          ) : null}
        </div>
      </div>

      {intro ? (
        <button type="button" className="player-pill player-skip" onClick={() => seek(intro.end_s)}>
          {t("media:player.skipIntro")}
          <Icon name="skip-forward" size={18} />
        </button>
      ) : credits && !finalCredits ? (
        <button type="button" className="player-pill player-skip" onClick={() => seek(credits.end_s)}>
          {t("media:player.skipCredits")}
          <Icon name="skip-forward" size={18} />
        </button>
      ) : null}

      {offerNext && item.next_id ? (
        <div className="player-next" role="dialog" aria-label={t("media:player.next.title")}>
          <p>
            {t("media:player.next.title")} · <strong>{item.next_label}</strong>
          </p>
          <div>
            <button
              type="button"
              className="player-pill"
              data-primary
              onClick={() => item.next_id && onEpisode(item.next_id)}
            >
              <Icon name="skip-forward" size={18} />
              {prefs.autoplayNext && !paused
                ? t("media:player.next.in", { seconds: countdown })
                : t("media:player.next.play")}
            </button>
            <button type="button" className="player-pill" onClick={() => setNextDismissed(true)}>
              {t("media:player.next.stay")}
            </button>
          </div>
        </div>
      ) : ended ? (
        <div className="player-ended" role="dialog" aria-label={t("media:player.ended")}>
          <button type="button" className="player-pill" data-primary onClick={() => seek(0)}>
            <Icon name="replay" size={18} />
            {t("media:player.replay")}
          </button>
          <button type="button" className="player-pill" onClick={onExit}>
            {t("media:player.back")}
          </button>
        </div>
      ) : null}

      <div className="player-bottom" aria-hidden={!visible}>
        <div
          className="player-bar"
          style={{ "--played": `${percent}%`, "--buffered": `${bufferedPercent}%` } as CSSProperties}
          onPointerMove={(event) => {
            const box = event.currentTarget.getBoundingClientRect();
            const fraction = Math.min(1, Math.max(0, (event.clientX - box.left) / box.width));
            setHover({ x: fraction * 100, at: fraction * total });
          }}
          onPointerLeave={() => setHover(null)}
        >
          {[...item.chapters.slice(1), ...item.markers].map((m) =>
            total > 0 ? (
              <span
                key={`${m.kind}-${m.start_s}`}
                className="player-mark"
                data-kind={m.kind}
                aria-hidden="true"
                style={
                  m.kind === "chapter"
                    ? { left: `${(m.start_s / total) * 100}%` }
                    : {
                        left: `${(m.start_s / total) * 100}%`,
                        width: `${((m.end_s - m.start_s) / total) * 100}%`,
                      }
                }
              />
            ) : null,
          )}
          {hoverChapter && total > 0 ? (
            <span
              className="player-chapter-hover"
              aria-hidden="true"
              style={{
                left: `${(hoverChapter.start_s / total) * 100}%`,
                width: `${((hoverChapter.end_s - hoverChapter.start_s) / total) * 100}%`,
              }}
            />
          ) : null}
          {hover ? (
            <span className="player-hover" style={{ left: `${hover.x}%` }} aria-hidden="true">
              {hoverPicture ? (
                <img src={hoverPicture} alt="" onError={(e) => e.currentTarget.remove()} />
              ) : null}
              {hoverChapter ? (
                <small>
                  {hoverChapter.label ??
                    t("media:player.chapter", { number: item.chapters.indexOf(hoverChapter) + 1 })}
                </small>
              ) : null}
              <span>{clock(hover.at)}</span>
            </span>
          ) : null}
          <input
            type="range"
            min={0}
            max={Math.max(1, Math.floor(total))}
            step={1}
            value={Math.floor(time)}
            onChange={(event) => seek(Number(event.target.value))}
            aria-label={t("media:player.position")}
            aria-valuetext={t("media:player.positionOf", { time: clock(time), total: clock(total) })}
          />
        </div>

        <div className="player-controls">
          <button
            type="button"
            className="player-icon player-main"
            onClick={toggle}
            aria-label={paused ? t("media:player.play") : t("media:player.pause")}
          >
            <Icon name={paused ? "play" : "pause"} size={28} />
          </button>
          <button
            type="button"
            className="player-icon"
            onClick={() => seek(time - 10)}
            aria-label={t("media:player.rewind")}
          >
            <Icon name="replay-10" size={22} />
          </button>
          <button
            type="button"
            className="player-icon"
            onClick={() => seek(time + 30)}
            aria-label={t("media:player.forward")}
          >
            <Icon name="forward-10" size={22} />
          </button>
          {item.previous_id ? (
            <button
              type="button"
              className="player-icon"
              onClick={() => item.previous_id && onEpisode(item.previous_id)}
              aria-label={t("media:player.previous")}
            >
              <Icon name="skip-back" size={22} />
            </button>
          ) : null}
          {item.next_id ? (
            <button
              type="button"
              className="player-icon"
              onClick={() => item.next_id && onEpisode(item.next_id)}
              aria-label={t("media:player.nextEpisode", { label: item.next_label ?? "" })}
            >
              <Icon name="skip-forward" size={22} />
            </button>
          ) : null}
          <div className="player-volume">
            <button
              type="button"
              className="player-icon"
              onClick={() => updatePrefs({ muted: !prefs.muted })}
              aria-label={prefs.muted ? t("media:player.unmute") : t("media:player.mute")}
            >
              <Icon
                name={
                  prefs.muted || prefs.volume === 0
                    ? "volume-off"
                    : prefs.volume < 0.5
                      ? "volume-low"
                      : "volume"
                }
                size={22}
              />
            </button>
            <input
              type="range"
              min={0}
              max={1}
              step={0.05}
              value={prefs.muted ? 0 : prefs.volume}
              onChange={(event) => updatePrefs({ volume: Number(event.target.value), muted: false })}
              aria-label={t("media:player.volume")}
              style={{ "--level": `${(prefs.muted ? 0 : prefs.volume) * 100}%` } as CSSProperties}
            />
          </div>
          <span className="player-time">
            {clock(time)} / {clock(total)}
          </span>
          <span className="player-spacer" />
          {textTracks.length ? (
            <button
              type="button"
              className="player-icon"
              data-on={Boolean(subtitle)}
              onClick={toggleSubtitles}
              aria-pressed={Boolean(subtitle)}
              aria-label={t("media:player.subtitles")}
              title={subtitleTrack?.label}
            >
              <Icon name="captions" size={22} />
            </button>
          ) : null}
          <div className="player-menu-anchor">
            <button
              type="button"
              className="player-icon"
              aria-expanded={menuOpen}
              aria-label={t("media:player.settings")}
              onClick={() => setMenuOpen((open) => !open)}
            >
              <Icon name="settings" size={22} />
            </button>
            {menuOpen ? (
              <SettingsMenu
                info={info}
                stream={stream}
                versionIndex={versionIndex}
                quality={quality}
                qualities={qualities}
                audio={audio}
                subtitle={subtitle}
                prefs={prefs}
                onVersion={(index) => {
                  setVersionIndex(index);
                  setAudio(initialAudio(item.versions[index]));
                  setSubtitle(null);
                }}
                onQuality={(key) => updatePrefs({ quality: key })}
                onAudio={setAudio}
                onSubtitle={(id) => {
                  setSubtitle(id);
                  const language = trackById(textTracks, id)?.language ?? null;
                  updatePrefs({ subtitleLanguage: id ? language : null });
                }}
                onPrefs={updatePrefs}
                onSeek={seek}
                onClose={() => setMenuOpen(false)}
              />
            ) : null}
          </div>
          {pipSupported ? (
            <button
              type="button"
              className="player-icon"
              onClick={togglePip}
              aria-label={t("media:player.pip")}
            >
              <Icon name="pip" size={22} />
            </button>
          ) : null}
          <button
            type="button"
            className="player-icon"
            onClick={toggleFullscreen}
            aria-label={fullscreen ? t("media:player.exitFullscreen") : t("media:player.fullscreen")}
          >
            <Icon name={fullscreen ? "exit-fullscreen" : "fullscreen"} size={22} />
          </button>
        </div>
      </div>
    </section>
  );
}
