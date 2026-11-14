import { Icon } from "../../design-system/components/Icon";
import { useFormat } from "../../i18n/format/useFormat";
import { useT } from "../../i18n/hooks/useT";
import { gamePictureUrl, playUrl, type RetroGame, type RetroRom, type SavedState } from "./api";
import "./resume.css";

/** A save state of one copy of the game (several ROMs of one game keep theirs apart). */
export type SavedEntry = SavedState & { rom: string; variant: string | null };

export function keyOf(entry: Pick<SavedEntry, "rom" | "slot">): string {
  return `${entry.rom}:${entry.slot}`;
}

/** Every copy of the game played here (one when the library has one). */
export function romsOf(game: RetroGame | undefined): RetroRom[] {
  return game?.roms ?? [];
}

/** The save states of every copy, latest first (slot 0, where the game was left, named so). */
export function entriesOf(game: RetroGame | undefined): SavedEntry[] {
  return romsOf(game)
    .flatMap((rom) =>
      rom.progress.states.map((state) => ({ ...state, rom: rom.id, variant: rom.variant ?? null })),
    )
    .sort((a, b) => b.updated_at.localeCompare(a.updated_at));
}

export function romName(rom: Pick<RetroRom, "platform" | "variant">): string {
  return [rom.platform.toUpperCase(), rom.variant].filter(Boolean).join(" · ");
}

/**
 * Issue 420: the member's save states of a game — each with the screen's picture, its slot, when it was
 * saved and, when the library holds several copies of the game, which one.
 */
export function SaveChooser({
  objectId,
  entries,
  selected,
  onSelect,
  label,
  copies,
}: {
  objectId: string;
  entries: SavedEntry[];
  selected?: string | null;
  onSelect(entry: SavedEntry): void;
  label: string;
  copies: boolean;
}) {
  const t = useT();
  const format = useFormat();
  return (
    <ul className="retro-chooser" aria-label={label}>
      {entries.map((entry) => {
        const name = entry.slot === 0 ? t("retro:saves.auto") : t("retro:saves.slot", { slot: entry.slot });
        return (
          <li key={keyOf(entry)}>
            <button
              type="button"
              className="retro-chooser__item"
              aria-pressed={selected === undefined ? undefined : selected === keyOf(entry)}
              onClick={() => onSelect(entry)}
            >
              <span className="retro-chooser__picture">
                {entry.has_picture ? (
                  <img
                    src={gamePictureUrl(objectId, entry.slot, entry.updated_at, entry.rom)}
                    alt=""
                    loading="lazy"
                  />
                ) : (
                  <Icon name="floppy" size={22} />
                )}
              </span>
              <span className="retro-chooser__text">
                <strong>{name}</strong>
                <small>{format.dateTime(entry.updated_at)}</small>
                {copies && entry.variant ? <small>{entry.variant}</small> : null}
              </span>
            </button>
          </li>
        );
      })}
    </ul>
  );
}

/** Issue 420: which copy of the game to start, when the library holds several (regions, revisions…). */
export function RomChooser({
  roms,
  selected,
  onSelect,
  label,
}: {
  roms: RetroRom[];
  selected: string | null;
  onSelect(rom: string): void;
  label: string;
}) {
  return (
    <ul className="retro-roms" aria-label={label}>
      {roms.map((rom) => (
        <li key={rom.id}>
          <button
            type="button"
            className="retro-chooser__item retro-roms__item"
            aria-pressed={selected === rom.id}
            onClick={() => onSelect(rom.id)}
          >
            <Icon name="joystick" size={18} />
            <span>{romName(rom)}</span>
          </button>
        </li>
      ))}
    </ul>
  );
}

/**
 * The game's page: « Resume » (the play page asks which save) and « New game » once something is saved, else
 * « Play here »; the saves always shown below — one of them opens the game on it at once.
 */
export function RetroPlayButtons({ objectId, game }: { objectId: string; game: RetroGame }) {
  const t = useT();
  const entries = entriesOf(game);
  const copies = romsOf(game).length > 1;
  return (
    <>
      {entries.length ? (
        <>
          <a className="ds-button ds-button--primary media-watch-here" href={playUrl(objectId)}>
            <Icon name="play" size={18} />
            {t("retro:cta.resume")}
          </a>
          <a className="ds-button ds-button--secondary" href={playUrl(objectId, { fresh: true })}>
            <Icon name="joystick" size={18} />
            {t("retro:newGame")}
          </a>
        </>
      ) : (
        <a
          className="ds-button ds-button--primary media-watch-here"
          href={playUrl(objectId, { fresh: true })}
        >
          <Icon name="joystick" size={18} />
          {t("retro:cta.play")}
        </a>
      )}
      {entries.length ? (
        <section className="retro-resume" aria-label={t("retro:saves.mine")}>
          <h3>{t("retro:saves.mine")}</h3>
          <SaveChooser
            objectId={objectId}
            entries={entries}
            label={t("retro:saves.mine")}
            copies={copies}
            onSelect={(entry) =>
              window.location.assign(playUrl(objectId, { resume: entry.slot, rom: entry.rom }))
            }
          />
        </section>
      ) : null}
    </>
  );
}
