import pegi3 from "../../../assets/ratings/pegi-3.svg";
import pegi7 from "../../../assets/ratings/pegi-7.svg";
import pegi12 from "../../../assets/ratings/pegi-12.svg";
import pegi16 from "../../../assets/ratings/pegi-16.svg";
import pegi18 from "../../../assets/ratings/pegi-18.svg";
import { Icon } from "../../../design-system/components/Icon";
import { useFormat } from "../../../i18n/format/useFormat";
import { useT } from "../../../i18n/hooks/useT";
import { useSection } from "../api";
import { useMeasures } from "../insights/api";

type Data = Record<string, unknown>;

function names(value: unknown): string[] {
  return Array.isArray(value) ? (value as unknown[]).filter((v): v is string => typeof v === "string") : [];
}

/**
 * Issue 476: a game's PEGI rating as its official mark (the label on the box: the age on green, amber or
 * red, « PEGI » beneath — public domain on Wikimedia Commons), read out as its age; any other rating system
 * as its words.
 */
const PEGI_MARKS: Record<number, string> = { 3: pegi3, 7: pegi7, 12: pegi12, 16: pegi16, 18: pegi18 };

export function AgeRating({ rating }: { rating: string }) {
  const t = useT();
  const age = Number(/PEGI\s*(\d{1,2})/i.exec(rating)?.[1]);
  const mark = PEGI_MARKS[age];
  if (!mark) return <span className="game-rating__text">{rating}</span>;
  return (
    <img
      className="game-rating__pegi"
      src={mark}
      alt={t("media:facts.pegi", { age })}
      title={t("media:facts.pegi", { age })}
      width={34}
      height={41}
    />
  );
}

/** Issue 351: how long a game takes by play style (HowLongToBeat, through RomM), as RomM's page shows it. */
const PLAY_STYLES = ["main_story", "main_plus_extra", "completionist", "all_styles"] as const;
export type PlayTimes = Partial<
  Record<(typeof PLAY_STYLES)[number], { seconds: number; players?: number | null }>
>;

export function PlayTimesFacts({ times }: { times: PlayTimes }) {
  const t = useT();
  const measures = useMeasures();
  const styles = PLAY_STYLES.filter((style) => times[style]?.seconds);
  if (!styles.length) return null;
  return (
    <section className="media-playtimes" aria-labelledby="media-playtimes-title">
      <h3 id="media-playtimes-title">
        <Icon name="clock" size={16} />
        {t("media:facts.playTimes")}
      </h3>
      <dl>
        {styles.map((style) => {
          const time = times[style];
          return (
            <div key={style}>
              <dt>{t(`media:facts.playTime.${style}`)}</dt>
              <dd>
                <strong>{measures.duration(Number(time?.seconds))}</strong>
                {typeof time?.players === "number" ? (
                  <span>{t("media:facts.playTimePlayers", { count: time.players })}</span>
                ) : null}
              </dd>
            </div>
          );
        })}
      </dl>
    </section>
  );
}

/** 027: a game's facts as the game database tells them, for a game the library lacks (issue 368): its
 * platform, publisher and studios, release date, tags and play times. */
export function GameFacts({ data }: { data: Data }) {
  const t = useT();
  const format = useFormat();
  const studios = names(data.people).filter((c) => c !== data.publisher);
  const rows = [
    data.platform ? { key: "platform", value: String(data.platform) } : null,
    data.publisher ? { key: "publisher", value: String(data.publisher) } : null,
    studios.length ? { key: "studios", value: studios.join(", ") } : null,
    data.released
      ? { key: "releasedOn", value: format.date(`${String(data.released)}T12:00:00Z`, "long") }
      : data.year
        ? { key: "releasedOn", value: String(data.year) }
        : null,
  ].filter((row) => row !== null);
  const tags = names(data.tags);
  const times = (data.play_times && typeof data.play_times === "object" ? data.play_times : {}) as PlayTimes;
  if (!rows.length && !tags.length && !Object.keys(times).length) return null;
  return (
    <>
      <dl className="media-facts">
        {rows.map((row) => (
          <div key={row.key}>
            <dt>{t(`media:facts.${row.key}`)}</dt>
            <dd>{row.value}</dd>
          </div>
        ))}
      </dl>
      {tags.length ? (
        <ul className="media-enriched__chips" aria-label={t("media:facts.tags")}>
          {tags.map((tag) => (
            <li key={tag}>{tag}</li>
          ))}
        </ul>
      ) : null}
      <PlayTimesFacts times={times} />
    </>
  );
}

/**
 * Issue 467 — a game's page laid out like a film's: its facts as chips (released, platform, how long its
 * story takes), its summary, its genres, then its production (studios, publisher, platform, release) and
 * its play times as blocks, and its tags — from what the library's services know (RomM). It comes above
 * the videos and pictures, as a film's details do.
 */
export function GameView({ objectId, genres }: { objectId: string; genres: string[] }) {
  const info = useSection(objectId, "info");
  if (!info.data) return null;
  return <GameDetails data={(info.data.data ?? {}) as Data} genres={genres} />;
}

export function GameDetails({ data, genres }: { data: Data; genres: string[] }) {
  const t = useT();
  const format = useFormat();
  const measures = useMeasures();
  const platform = data.platform ? String(data.platform) : null;
  const released = data.released ? format.date(`${String(data.released)}T12:00:00Z`, "long") : null;
  const times = (data.play_times && typeof data.play_times === "object" ? data.play_times : {}) as PlayTimes;
  const story = times.main_story?.seconds ?? times.all_styles?.seconds;
  const facts = [
    released ? { key: "released", icon: "calendar", value: released } : null,
    platform ? { key: "platform", icon: "gamepad", value: platform } : null,
    story ? { key: "length", icon: "clock", value: measures.duration(Number(story)) } : null,
  ].filter((fact) => fact !== null);
  const companies = names(data.people);
  const studios = companies.filter((name) => name !== data.publisher);
  const rating = data.content_rating ? String(data.content_rating) : null;
  const production = [
    studios.length ? { key: "studios", value: studios.join(", ") } : null,
    data.publisher ? { key: "publisher", value: String(data.publisher) } : null,
    platform ? { key: "platform", value: platform } : null,
    released
      ? { key: "releasedOn", value: released }
      : data.year
        ? { key: "releasedOn", value: String(data.year) }
        : null,
    rating ? { key: "ageRating", value: <AgeRating rating={rating} /> } : null,
  ].filter((row) => row !== null);
  const shownGenres = genres.filter((genre) => genre !== platform);
  const tags = names(data.tags).filter((tag) => !shownGenres.includes(tag));
  const timed = Object.values(times).some((time) => time?.seconds);
  if (!facts.length && !data.overview && !shownGenres.length && !production.length && !tags.length && !timed)
    return null;
  return (
    <section className="media-enriched" aria-label={t("media:detail.section.info")}>
      {data.original_title && data.original_title !== data.title ? (
        <p className="media-enriched__tagline">{String(data.original_title)}</p>
      ) : null}
      {facts.length ? (
        <ul className="media-enriched__facts">
          {facts.map((fact) => (
            <li key={fact.key}>
              <Icon name={fact.icon} size={16} />
              {fact.value}
            </li>
          ))}
        </ul>
      ) : null}
      {data.overview ? <p className="media-enriched__overview">{String(data.overview)}</p> : null}
      {shownGenres.length ? (
        <ul className="media-enriched__chips" aria-label={t("media:enriched.genres")}>
          {shownGenres.map((genre) => (
            <li key={genre}>{genre}</li>
          ))}
        </ul>
      ) : null}
      {production.length || timed ? (
        <div className="media-enriched__grid">
          {production.length ? (
            <div className="media-enriched__block">
              <h3>{t("media:enriched.production")}</h3>
              <dl className="media-enriched__pairs">
                {production.map((row) => (
                  <div key={row.key}>
                    <dt>{t(`media:facts.${row.key}`)}</dt>
                    <dd>{row.value}</dd>
                  </div>
                ))}
              </dl>
            </div>
          ) : null}
          {timed ? (
            <div className="media-enriched__block media-enriched__block--times">
              <PlayTimesFacts times={times} />
            </div>
          ) : null}
        </div>
      ) : null}
      {tags.length ? (
        <ul className="media-enriched__chips media-enriched__chips--quiet" aria-label={t("media:facts.tags")}>
          {tags.map((tag) => (
            <li key={tag}>#{tag}</li>
          ))}
        </ul>
      ) : null}
    </section>
  );
}
