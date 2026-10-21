import { type FormEvent, useEffect, useRef, useState } from "react";
import { Icon } from "../../../design-system/components/Icon";
import { useT } from "../../../i18n/hooks/useT";
import { ApiError } from "../../../state/regions";
import { askRadio, coverUrl, type Radio, type RadioRequest, radioRequest } from "./api";
import { useRadioPlayback, useRadioToggle } from "./store";
import "./radio.css";

/**
 * Issue 168: the homelab's radio — the track on air with its cover, listen or stop (it keeps playing while
 * browsing), and ask its DJ for a song, a vibe or « more like this »: the request is followed until the DJ
 * queued it (or says why not). ``compact``: one line (a small widget).
 */
export function RadioCard({
  radio,
  compact = false,
  history = false,
}: {
  radio: Radio;
  compact?: boolean;
  history?: boolean;
}) {
  const t = useT();
  const playback = useRadioPlayback();
  const toggle = useRadioToggle();
  const current = radio.current ?? null;
  const cover = coverUrl(current);
  const on = playback.playing || playback.loading;
  const play = (
    <button
      type="button"
      className="radio-card__play"
      aria-pressed={on}
      aria-label={on ? t("media:radio.stop") : t("media:radio.listen")}
      title={on ? t("media:radio.stop") : t("media:radio.listen")}
      onClick={toggle}
      disabled={!radio.on_air}
    >
      <Icon name={playback.loading ? "radio" : on ? "pause" : "play"} size={compact ? 18 : 22} />
    </button>
  );
  return (
    <div
      className="radio-card"
      data-compact={compact || undefined}
      data-playing={playback.playing || undefined}
    >
      <div className="radio-card__now">
        <span className="radio-card__cover" aria-hidden="true">
          {cover ? <img src={cover} alt="" loading="lazy" /> : <Icon name="radio" size={compact ? 18 : 28} />}
          {playback.playing ? (
            <span className="radio-card__eq">
              <span />
              <span />
              <span />
            </span>
          ) : null}
        </span>
        <div className="radio-card__text">
          <p className="radio-card__station">
            <span className="radio-card__live" data-on={radio.on_air || undefined}>
              {radio.on_air ? t("media:radio.live") : t("media:radio.offAir")}
            </span>
            {radio.station}
            {radio.host ? (
              <span className="radio-card__host"> · {t("media:radio.host", { name: radio.host })}</span>
            ) : null}
          </p>
          <p className="radio-card__title">{current?.title ?? t("media:radio.nothing")}</p>
          {current?.artist ? (
            <p className="radio-card__artist">
              {[current.artist, current.album].filter(Boolean).join(" — ")}
              {current.requested_by ? (
                <span className="radio-card__by">
                  {" "}
                  · {t("media:radio.askedBy", { name: current.requested_by })}
                </span>
              ) : null}
            </p>
          ) : null}
        </div>
        {play}
      </div>
      {playback.failed ? (
        <p className="radio-card__note" role="status">
          {t("media:radio.failed")}
        </p>
      ) : null}
      {compact ? null : <AskForm />}
      {history && radio.recent?.length ? (
        <section className="radio-card__history" aria-label={t("media:radio.recent")}>
          <h3>{t("media:radio.recent")}</h3>
          <ol>
            {(radio.recent ?? []).slice(0, 8).map((track, index) => (
              // biome-ignore lint/suspicious/noArrayIndexKey: the order they played in
              <li key={index}>
                <span className="radio-card__mini-cover" aria-hidden="true">
                  {coverUrl(track) ? (
                    <img src={coverUrl(track) ?? ""} alt="" loading="lazy" />
                  ) : (
                    <Icon name="music" size={14} />
                  )}
                </span>
                <span className="radio-card__track">
                  <strong>{track.title}</strong>
                  {track.artist ? <span>{track.artist}</span> : null}
                </span>
              </li>
            ))}
          </ol>
        </section>
      ) : null}
    </div>
  );
}

const POLL_MS = 3000;
const POLL_FOR_MS = 90_000;

function AskForm() {
  const t = useT();
  const [text, setText] = useState("");
  const [request, setRequest] = useState<RadioRequest | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const started = useRef(0);
  // follow the request until the DJ queued it, refused it, or the wait is over
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
    } catch (caught) {
      const code = caught instanceof ApiError ? caught.code : null;
      setError(code === "media.radio_too_soon" ? t("media:radio.tooSoon") : t("media:radio.askFailed"));
    } finally {
      setBusy(false);
    }
  };
  return (
    <form className="radio-card__ask" onSubmit={(event) => void submit(event)}>
      <label className="visually-hidden" htmlFor="radio-ask">
        {t("media:radio.askLabel")}
      </label>
      <input
        id="radio-ask"
        className="radio-card__input"
        value={text}
        maxLength={280}
        placeholder={t("media:radio.askPlaceholder")}
        onChange={(event) => setText(event.target.value)}
      />
      <button
        type="submit"
        className="radio-card__send"
        disabled={busy || !text.trim()}
        aria-label={t("media:radio.ask")}
        title={t("media:radio.ask")}
      >
        <Icon name="send" size={16} />
      </button>
      {error ? (
        <p className="radio-card__note" role="alert">
          {error}
        </p>
      ) : request ? (
        <p className="radio-card__note" role="status" data-status={request.status}>
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
