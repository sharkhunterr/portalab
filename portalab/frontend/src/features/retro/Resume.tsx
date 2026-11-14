import { useState } from "react";
import { Icon } from "../../design-system/components/Icon";
import { useFormat } from "../../i18n/format/useFormat";
import { useT } from "../../i18n/hooks/useT";
import { gamePictureUrl, playUrl, type RetroGame, type SavedState } from "./api";
import "./resume.css";

/** The save states, latest first (slot 0, where the game was left, named so). */
export function statesOf(game: RetroGame | undefined): SavedState[] {
  return [...(game?.progress?.states ?? [])].sort((a, b) => b.updated_at.localeCompare(a.updated_at));
}

/**
 * Issue 420: the member's save states of a game, to choose where to resume — each with the screen's picture,
 * its slot and when it was saved.
 */
export function SaveChooser({
  objectId,
  states,
  selected,
  onSelect,
  label,
}: {
  objectId: string;
  states: SavedState[];
  selected?: number | null;
  onSelect(slot: number): void;
  label: string;
}) {
  const t = useT();
  const format = useFormat();
  return (
    <ul className="retro-chooser" aria-label={label}>
      {states.map((state) => {
        const name = state.slot === 0 ? t("retro:saves.auto") : t("retro:saves.slot", { slot: state.slot });
        return (
          <li key={state.slot}>
            <button
              type="button"
              className="retro-chooser__item"
              aria-pressed={selected === undefined ? undefined : selected === state.slot}
              onClick={() => onSelect(state.slot)}
            >
              <span className="retro-chooser__picture">
                {state.has_picture ? (
                  <img src={gamePictureUrl(objectId, state.slot, state.updated_at)} alt="" loading="lazy" />
                ) : (
                  <Icon name="floppy" size={22} />
                )}
              </span>
              <span className="retro-chooser__text">
                <strong>{name}</strong>
                <small>{format.dateTime(state.updated_at)}</small>
              </span>
            </button>
          </li>
        );
      })}
    </ul>
  );
}

/** The game's page: « Resume » (choosing the save) and « New game » once something is saved, else « Play here ». */
export function RetroPlayButtons({ objectId, game }: { objectId: string; game: RetroGame }) {
  const t = useT();
  const [choosing, setChoosing] = useState(false);
  const states = statesOf(game);
  if (!states.length) {
    return (
      <a className="ds-button ds-button--primary media-watch-here" href={playUrl(objectId, null)}>
        <Icon name="joystick" size={18} />
        {t("retro:cta.play")}
      </a>
    );
  }
  return (
    <>
      <button
        type="button"
        className="ds-button ds-button--primary media-watch-here"
        aria-expanded={choosing}
        onClick={() => setChoosing((open) => !open)}
      >
        <Icon name="play" size={18} />
        {t("retro:cta.resume")}
      </button>
      <a className="ds-button ds-button--secondary" href={playUrl(objectId, null)}>
        <Icon name="joystick" size={18} />
        {t("retro:newGame")}
      </a>
      {choosing ? (
        <div className="retro-resume">
          <p>{t("retro:resume.choose")}</p>
          <SaveChooser
            objectId={objectId}
            states={states}
            label={t("retro:resume.choose")}
            onSelect={(slot) => window.location.assign(playUrl(objectId, slot))}
          />
        </div>
      ) : null}
    </>
  );
}
