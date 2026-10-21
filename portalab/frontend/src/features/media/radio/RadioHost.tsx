import * as DialogPrimitive from "@radix-ui/react-dialog";
import { useQueryClient } from "@tanstack/react-query";
import { type FormEvent, useEffect, useRef, useState } from "react";
import { Link } from "react-router";
import { Icon } from "../../../design-system/components/Icon";
import { useT } from "../../../i18n/hooks/useT";
import { ApiError } from "../../../state/regions";
import { useListen } from "../listen/store";
import {
  askRadio,
  coverUrl,
  RADIO_KEY,
  type RadioRequest,
  type RadioTrack,
  radioRequest,
  useRadio,
} from "./api";
import {
  closeRadio,
  expandRadio,
  setRadioVolume,
  stopRadio,
  useRadioPlayback,
  useRadioToggle,
} from "./store";
import "../player/player.css";
import "../listen/listen.css";
import "./radio.css";

/**
 * Issue 168: the radio in the portal's audio player — the same bar at the bottom and the same bigger view
 * as an audiobook's (music will share it): the track on air and its cover, play or pause (live), the
 * volume; in the bigger view, ask the DJ for a song and follow the request, what comes next and what
 * played. Mounted once by the shell; an audiobook opening closes it.
 */
export function RadioHost() {
  const playback = useRadioPlayback();
  const book = useListen();
  useEffect(() => {
    if (book.objectId && playback.open) closeRadio(); // one player at a time
  }, [book.objectId, playback.open]);
  if (!playback.open) return null;
  return (
    <>
      <RadioBar />
      <RadioStage />
    </>
  );
}

function Cover({ track, size }: { track: RadioTrack | null | undefined; size: "small" | "large" }) {
  const src = coverUrl(track);
  return (
    <span className="listen-cover radio-cover" data-size={size}>
      {src ? <img src={src} alt="" /> : <Icon name="radio" size={size === "large" ? 64 : 22} />}
    </span>
  );
}

function RadioBar() {
  const t = useT();
  const playback = useRadioPlayback();
  const toggle = useRadioToggle();
  const radio = useRadio().data;
  const current = radio?.current ?? null;
  const on = playback.playing || playback.loading;
  return (
    <section className="listen-mini radio-mini" aria-label={t("media:radio.player")}>
      <span
        className="listen-mini__progress radio-mini__live"
        aria-hidden="true"
        data-on={playback.playing || undefined}
      >
        <span />
      </span>
      <button
        type="button"
        className="listen-mini__open"
        onClick={() => expandRadio(true)}
        aria-label={t("media:radio.expand")}
      >
        <Cover track={current} size="small" />
        <span className="listen-mini__text">
          <strong>{current?.title ?? radio?.station ?? t("media:radio.title")}</strong>
          <small>
            {playback.failed
              ? t("media:radio.failed")
              : [current?.artist, radio?.station].filter(Boolean).join(" · ")}
          </small>
        </span>
      </button>
      <span className="listen-mini__controls">
        <span className="radio-live" data-on={playback.playing || undefined}>
          {t("media:radio.live")}
        </span>
        <button
          type="button"
          className="listen-mini__play"
          onClick={toggle}
          aria-label={on ? t("media:radio.stop") : t("media:radio.listen")}
          data-buffering={playback.loading || undefined}
          disabled={radio ? !radio.on_air : false}
        >
          <Icon name={on ? "pause" : "play"} size={22} />
        </button>
        <button
          type="button"
          className="listen-mini__close"
          onClick={closeRadio}
          aria-label={t("media:radio.close")}
        >
          <Icon name="close" size={18} />
        </button>
      </span>
    </section>
  );
}

function RadioStage() {
  const t = useT();
  const playback = useRadioPlayback();
  const toggle = useRadioToggle();
  const radio = useRadio().data;
  const current = radio?.current ?? null;
  const on = playback.playing || playback.loading;
  return (
    <DialogPrimitive.Root open={playback.expanded} onOpenChange={(open) => expandRadio(open)}>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Content className="listen-stage radio-stage" aria-describedby={undefined}>
          <div className="player-top listen-stage__top">
            <button
              type="button"
              className="player-icon"
              onClick={() => expandRadio(false)}
              aria-label={t("media:radio.collapse")}
            >
              <Icon name="chevron-down" size={24} />
            </button>
            <DialogPrimitive.Title className="player-title">
              <strong>{radio?.station ?? t("media:radio.title")}</strong>
              <span>
                {[radio?.host ? t("media:radio.host", { name: radio.host }) : null, radio?.tagline]
                  .filter(Boolean)
                  .join(" — ")}
              </span>
            </DialogPrimitive.Title>
            <span className="radio-live" data-on={playback.playing || undefined}>
              {radio?.on_air ? t("media:radio.live") : t("media:radio.offAir")}
            </span>
          </div>

          <div className="listen-stage__body">
            <div className="listen-stage__art">
              <Cover track={current} size="large" />
              <p className="listen-stage__chapter">{current?.title ?? t("media:radio.nothing")}</p>
              {current?.artist ? (
                <p className="listen-stage__muted">
                  {[current.artist, current.album, current.year].filter(Boolean).join(" — ")}
                </p>
              ) : null}
              {current?.requested_by ? (
                <p className="listen-stage__muted">
                  <Icon name="heart" size={14} />
                  {t("media:radio.askedBy", { name: current.requested_by })}
                </p>
              ) : null}
            </div>

            <aside className="listen-stage__panel radio-stage__panel" aria-label={t("media:radio.title")}>
              <section>
                <h3>{t("media:radio.askTitle")}</h3>
                <AskForm />
              </section>
              {radio?.upcoming?.length ? (
                <section>
                  <h3>{t("media:radio.upcoming")}</h3>
                  <Tracks tracks={radio.upcoming} />
                </section>
              ) : null}
              {radio?.recent?.length ? (
                <section>
                  <h3>{t("media:radio.recent")}</h3>
                  <Tracks tracks={radio.recent.slice(0, 10)} />
                </section>
              ) : null}
            </aside>
          </div>

          <div className="player-bottom listen-stage__bottom">
            <div className="player-controls">
              <button
                type="button"
                className="player-icon player-main"
                onClick={toggle}
                aria-label={on ? t("media:radio.stop") : t("media:radio.listen")}
                disabled={radio ? !radio.on_air : false}
              >
                <Icon name={on ? "pause" : "play"} size={28} />
              </button>
              <span className="player-time">
                {playback.failed
                  ? t("media:radio.failed")
                  : playback.loading
                    ? t("media:radio.tuning")
                    : radio?.listeners
                      ? t("media:radio.listeners", { count: radio.listeners })
                      : ""}
              </span>
              <span className="player-spacer" />
              <label className="listen-stage__option radio-stage__volume">
                <Icon name={playback.volume ? "volume" : "volume-off"} size={16} />
                <input
                  type="range"
                  min={0}
                  max={1}
                  step={0.05}
                  value={playback.volume}
                  aria-label={t("media:radio.volume")}
                  onChange={(event) => setRadioVolume(Number(event.target.value))}
                />
              </label>
              <button
                type="button"
                className="player-icon"
                onClick={() => {
                  stopRadio();
                  closeRadio();
                }}
                aria-label={t("media:radio.close")}
                title={t("media:radio.close")}
              >
                <Icon name="close" size={20} />
              </button>
            </div>
          </div>
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  );
}

function Tracks({ tracks }: { tracks: RadioTrack[] }) {
  const t = useT();
  return (
    <ol className="radio-tracks">
      {tracks.map((track, index) => (
        // biome-ignore lint/suspicious/noArrayIndexKey: the order they played (or will play) in
        <li key={index}>
          <Cover track={track} size="small" />
          <span className="radio-tracks__text">
            <strong>{track.title}</strong>
            <small>
              {[
                track.artist,
                track.requested_by ? t("media:radio.askedBy", { name: track.requested_by }) : null,
              ]
                .filter(Boolean)
                .join(" · ")}
            </small>
          </span>
        </li>
      ))}
    </ol>
  );
}

const POLL_MS = 3000;
const POLL_FOR_MS = 90_000;

/** Ask the DJ for a song, a vibe or « more like this » — followed until it is queued (or why not). */
export function AskForm({ autoFocus = false }: { autoFocus?: boolean }) {
  const t = useT();
  const client = useQueryClient();
  const allowance = useRadio().data?.allowance ?? null;
  const [noCredits, setNoCredits] = useState(false);
  const [text, setText] = useState("");
  const [request, setRequest] = useState<RadioRequest | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const started = useRef(0);
  useEffect(() => {
    if (!request?.id || request.status !== "pending") return;
    if (Date.now() - started.current > POLL_FOR_MS) return;
    const timer = window.setTimeout(() => {
      void radioRequest(request.id as string)
        .then(setRequest)
        .catch(() => undefined);
    }, POLL_MS);
    return () => window.clearTimeout(timer);
  }, [request]);
  const submit = async (event: FormEvent) => {
    event.preventDefault();
    const asked = text.trim();
    if (!asked || busy) return;
    setBusy(true);
    setError(null);
    try {
      started.current = Date.now();
      const answer = await askRadio(asked);
      setRequest(answer);
      if (answer.status !== "failed") setText("");
      void client.invalidateQueries({ queryKey: RADIO_KEY }); // what is left to ask today
    } catch (caught) {
      const code = caught instanceof ApiError ? caught.code : null;
      setNoCredits(code === "media.radio_no_credits");
      setError(
        code === "media.radio_too_soon"
          ? t("media:radio.tooSoon")
          : code === "media.radio_no_credits"
            ? t("media:radio.noCredits")
            : t("media:radio.askFailed"),
      );
    } finally {
      setBusy(false);
    }
  };
  return (
    <form className="radio-ask" onSubmit={(event) => void submit(event)}>
      <label className="visually-hidden" htmlFor="radio-ask">
        {t("media:radio.askLabel")}
      </label>
      <input
        id="radio-ask"
        className="radio-ask__input"
        value={text}
        maxLength={280}
        // biome-ignore lint/a11y/noAutofocus: opened on purpose to ask (« Ask the DJ »)
        autoFocus={autoFocus}
        placeholder={t("media:radio.askPlaceholder")}
        onChange={(event) => setText(event.target.value)}
      />
      <button
        type="submit"
        className="radio-ask__send"
        disabled={busy || !text.trim()}
        aria-label={t("media:radio.ask")}
        title={t("media:radio.ask")}
      >
        <Icon name="send" size={16} />
      </button>
      {allowance ? (
        <p className="radio-ask__allowance">
          {t("media:radio.allowance", { free: allowance.free_left, credits: allowance.credits })}
          {allowance.free_left === 0 && allowance.credits === 0 ? (
            <>
              {" "}
              <Link to="/marketplace?type=radio_requests" onClick={() => expandRadio(false)}>
                {t("media:radio.buyCredits")}
              </Link>
            </>
          ) : null}
        </p>
      ) : null}
      {error ? (
        <p className="radio-ask__note" role="alert">
          {error}
          {noCredits ? (
            <>
              {" "}
              <Link to="/marketplace?type=radio_requests" onClick={() => expandRadio(false)}>
                {t("media:radio.buyCredits")}
              </Link>
            </>
          ) : null}
        </p>
      ) : request ? (
        <p className="radio-ask__note" role="status" data-status={request.status}>
          {request.status === "queued"
            ? request.track
              ? t("media:radio.queuedTrack", { title: request.track.title })
              : t("media:radio.queued")
            : request.status === "failed"
              ? request.detail || t("media:radio.refused")
              : request.status === "unknown"
                ? t("media:radio.lost")
                : t("media:radio.pending")}
        </p>
      ) : null}
    </form>
  );
}
