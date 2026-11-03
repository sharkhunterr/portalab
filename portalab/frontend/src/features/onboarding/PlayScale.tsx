import { type CSSProperties, useId } from "react";
import { Icon } from "../../design-system/components/Icon";
import { useT } from "../../i18n/hooks/useT";
import { PLAY, PLAY_FEATURES, type Play, playIndex } from "./play";

/**
 * Issue 347: the play gauge — a slider from « just the media » to « keen », each notch named under it, and
 * what the chosen one brings: every feature from its notch on is ticked, the others shown greyed out.
 */
export function PlayScale({
  value,
  onChange,
  disabled,
}: {
  value: Play;
  onChange: (play: Play) => void;
  disabled?: boolean;
}) {
  const t = useT();
  const id = useId();
  const at = playIndex(value);
  const icon = PLAY[at]?.icon ?? "game";
  return (
    <fieldset className="play-scale" disabled={disabled} data-play={value}>
      <legend className="visually-hidden">{t("onboarding:play.title")}</legend>
      <input
        id={id}
        type="range"
        className="play-scale__range"
        min={0}
        max={PLAY.length - 1}
        step={1}
        value={at}
        aria-label={t("onboarding:play.gauge")}
        aria-valuetext={t(`onboarding:play.${value}`)}
        style={{ "--play-fill": `${(at / (PLAY.length - 1)) * 100}%` } as CSSProperties}
        onChange={(event) => onChange(PLAY[Number(event.target.value)]?.key ?? value)}
      />
      <ol className="play-scale__stops">
        {PLAY.map((stop) => (
          <li key={stop.key}>
            <button
              type="button"
              aria-pressed={stop.key === value}
              onClick={() => onChange(stop.key)}
              className="play-scale__stop"
            >
              <Icon name={stop.icon} size={18} />
              <span>{t(`onboarding:play.${stop.key}`)}</span>
            </button>
          </li>
        ))}
      </ol>
      <div className="play-scale__card" aria-live="polite">
        <p className="play-scale__name">
          <Icon name={icon} size={18} />
          <strong>{t(`onboarding:play.${value}`)}</strong>
        </p>
        <p className="play-scale__hint">{t(`onboarding:play.${value}Hint`)}</p>
        <ul className="play-scale__features">
          {PLAY_FEATURES.map((feature) => {
            const on = playIndex(feature.from) <= at;
            return (
              <li key={feature.key} className="play-scale__feature" data-on={on || undefined}>
                <span className="play-scale__mark">
                  <Icon name={on ? "check" : "minus"} size={14} />
                </span>
                <span>{t(`onboarding:play.feature.${feature.key}`)}</span>
              </li>
            );
          })}
        </ul>
      </div>
    </fieldset>
  );
}
