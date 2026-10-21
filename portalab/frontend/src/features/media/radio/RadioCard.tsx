import { Icon } from "../../../design-system/components/Icon";
import { useT } from "../../../i18n/hooks/useT";
import { coverUrl, type Radio } from "./api";
import { expandRadio, useRadioPlayback, useRadioToggle } from "./store";
import "./radio.css";

/**
 * Issue 168: the homelab's radio where it is shown (a widget, the Media page) — the track on air with its
 * cover, listen or pause, and the way into the portal's audio player: its bigger view holds the request to
 * the DJ, what comes next and what played. ``compact``: one line (a small widget).
 */
export function RadioCard({ radio, compact = false }: { radio: Radio; compact?: boolean }) {
  const t = useT();
  const playback = useRadioPlayback();
  const toggle = useRadioToggle();
  const current = radio.current ?? null;
  const cover = coverUrl(current);
  const on = playback.playing || playback.loading;
  return (
    <div
      className="radio-card"
      data-compact={compact || undefined}
      data-playing={playback.playing || undefined}
    >
      <div className="radio-card__now">
        <button
          type="button"
          className="radio-card__cover"
          onClick={() => expandRadio(true)}
          aria-label={t("media:radio.expand")}
          title={t("media:radio.expand")}
        >
          {cover ? <img src={cover} alt="" loading="lazy" /> : <Icon name="radio" size={compact ? 18 : 28} />}
          {playback.playing ? (
            <span className="radio-card__eq" aria-hidden="true">
              <span />
              <span />
              <span />
            </span>
          ) : null}
        </button>
        <div className="radio-card__text">
          <p className="radio-card__station">
            <span className="radio-live" data-on={radio.on_air || undefined}>
              {radio.on_air ? t("media:radio.live") : t("media:radio.offAir")}
            </span>
            {radio.station}
            {radio.host ? <span> · {t("media:radio.host", { name: radio.host })}</span> : null}
          </p>
          <p className="radio-card__title">{current?.title ?? t("media:radio.nothing")}</p>
          {current?.artist && !compact ? (
            <p className="radio-card__artist">
              {[current.artist, current.album].filter(Boolean).join(" — ")}
            </p>
          ) : null}
        </div>
        <button
          type="button"
          className="radio-card__play"
          aria-pressed={on}
          aria-label={on ? t("media:radio.stop") : t("media:radio.listen")}
          title={on ? t("media:radio.stop") : t("media:radio.listen")}
          onClick={toggle}
          disabled={!radio.on_air}
        >
          <Icon name={on ? "pause" : "play"} size={compact ? 18 : 22} />
        </button>
      </div>
      {compact ? null : (
        <div className="radio-card__actions">
          <button type="button" className="radio-card__action" onClick={() => expandRadio(true)}>
            <Icon name="message" size={14} />
            {t("media:radio.askTitle")}
          </button>
          <button type="button" className="radio-card__action" onClick={() => expandRadio(true)}>
            <Icon name="list" size={14} />
            {t("media:radio.openPlayer")}
          </button>
        </div>
      )}
    </div>
  );
}
