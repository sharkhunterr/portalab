import { type CSSProperties, useEffect, useRef, useState } from "react";
import { Link } from "react-router";
import { Icon } from "../../../design-system/components/Icon";
import { useFormat } from "../../../i18n/format/useFormat";
import { useT } from "../../../i18n/hooks/useT";
import { metadataImage } from "../../media/detail/Enrichment";
import { useMeasures } from "../../media/insights/api";
import { WidgetHeaderAction } from "../frame/actions";
import { PosterStrip } from "./compact";
import { TitleFacts } from "./facts";
import { reducedMotion, useLively } from "./motion";
import { registerWidgetComponent, type WidgetProps } from "./registry";
import "./skins.css";

/**
 * 027 (#31): three media widgets — the « living wall » (posters turning one by one, sold in the shop),
 * « playing on the server » (what runs now, titles and progress, never who) and « a year ago » (what I
 * watched around this date, and what came into the library).
 */
interface Card {
  id: string | null;
  title: string;
  subtitle?: string | null;
  kind?: string;
  state?: string;
  progress?: number | null;
  mine?: boolean;
  at?: string;
  image_id: string | null;
  poster_ref?: string | null;
  route: string | null;
}

const art = (card: Card): string | null =>
  card.image_id ? `/api/v1/media/images/${card.image_id}` : metadataImage(card.poster_ref, "w342");
const KIND_ICON: Record<string, string> = {
  movie: "film",
  episode: "tv",
  series: "tv",
  track: "music",
  live: "tv",
};

// --- living wall ---------------------------------------------------------------------------------------------
const TILES = 24;

function Tile({ card }: { card: Card }) {
  const src = art(card);
  return src ? (
    <img src={src} alt="" loading="lazy" />
  ) : (
    <span className="widget-living-wall__title">{card.title}</span>
  );
}

function LivingWall({ payload, compact }: WidgetProps) {
  const ref = useRef<HTMLUListElement>(null);
  const lively = useLively(ref);
  const cards = ((payload.data ?? {}) as { items?: Card[] }).items ?? [];
  const total = cards.length;
  const count = Math.min(TILES, Math.max(0, total - 1));
  // each tile shows one card; a flip turns a tile to a card not on the wall
  const [shown, setShown] = useState<number[]>(() => Array.from({ length: count }, (_, i) => i));
  const [flipped, setFlipped] = useState<number | null>(null);
  useEffect(() => setShown(Array.from({ length: count }, (_, i) => i)), [count]);
  useEffect(() => {
    if (!lively || total <= count || count === 0) return;
    const timer = window.setInterval(() => {
      setShown((tiles) => {
        const tile = Math.floor(Math.random() * tiles.length);
        const free = Array.from({ length: total }, (_, i) => i).filter((i) => !tiles.includes(i));
        const next = free[Math.floor(Math.random() * free.length)];
        if (next === undefined) return tiles;
        setFlipped(tile);
        return tiles.map((card, i) => (i === tile ? next : card));
      });
    }, 2600);
    return () => window.clearInterval(timer);
  }, [lively, total, count]);
  if (compact)
    // 027 (#36): on a single row, the wall becomes a running frieze
    return (
      <PosterStrip
        cards={cards.map((card, index) => ({
          key: `${card.id ?? card.title}-${index}`,
          title: card.title,
          src: art(card),
          to: card.route,
        }))}
        running
      />
    );
  if (!count) return null;
  return (
    <ul
      ref={ref}
      className="widget-living-wall"
      data-nofit
      data-still={!lively || reducedMotion() || undefined}
    >
      {shown.map((index, tile) => {
        const card = cards[index] as Card;
        return (
          <li
            // the tile keeps its place; its key changes with its card so the new one flips in
            // biome-ignore lint/suspicious/noArrayIndexKey: a tile is its place on the wall
            key={`${tile}-${card.id ?? card.title}`}
            data-flip={flipped === tile || undefined}
            title={card.title}
          >
            {card.route ? (
              <Link to={card.route} aria-label={card.title}>
                <Tile card={card} />
              </Link>
            ) : (
              <Tile card={card} />
            )}
          </li>
        );
      })}
    </ul>
  );
}

// --- playing on the server -----------------------------------------------------------------------------------
interface Playing extends Card {
  remaining_s?: number | null;
  /** #47: live TV — no end to reach, a channel instead */
  live?: boolean;
  channel?: string | null;
  year?: number | null;
  genres?: string[] | null;
  rating?: number | null;
  overview?: string | null;
}

function StateIcon({ state }: { state?: string | undefined }) {
  return (
    <Icon name={state === "paused" ? "pause" : state === "buffering" ? "hourglass" : "play"} size={11} />
  );
}

/** A session's progress: the bar, then how far and how long is left. */
function Progress({ card }: { card: Playing }) {
  const t = useT();
  const format = useFormat();
  const measures = useMeasures();
  const percent =
    card.progress !== null && card.progress !== undefined ? Math.round(card.progress * 100) : null;
  if (percent === null) return null;
  return (
    <span className="widget-playing__progress">
      <span
        className="widget-playing__bar"
        role="progressbar"
        aria-valuenow={percent}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={card.title}
      >
        <span style={{ inlineSize: `${percent}%` }} />
      </span>
      <small>
        {format.percent(percent / 100)}
        {card.remaining_s
          ? ` · ${t("media:widget.server_playing.left", { time: measures.duration(card.remaining_s) })}`
          : ""}
      </small>
    </span>
  );
}

function PlayingCard({ card, hero = false }: { card: Playing; hero?: boolean }) {
  const t = useT();
  const src = art(card);
  const body = (
    <>
      <span className="widget-playing__poster">
        {src ? (
          <img src={src} alt="" loading="lazy" />
        ) : (
          <Icon name={KIND_ICON[card.kind ?? ""] ?? "film"} size={22} />
        )}
      </span>
      <span className="widget-playing__info">
        <span className="widget-playing__state" data-playback={card.state}>
          <StateIcon state={card.state} />
          {t(
            card.state === "paused" || card.state === "buffering"
              ? `media:widget.server_playing.${card.state}`
              : "media:widget.server_playing.playing",
          )}
          {card.mine ? (
            <span className="widget-server-playing__you">{t("media:widget.server_playing.you")}</span>
          ) : null}
        </span>
        <strong className="widget-playing__title">{card.title}</strong>
        {card.subtitle ? <small className="widget-playing__subtitle">{card.subtitle}</small> : null}
        {hero ? <TitleFacts facts={{ ...card, kind: card.kind }} /> : null}
        {card.live ? (
          // #47: live TV — the channel and « live », where a film shows how far it got
          <span className="widget-playing__live">
            <span className="widget-playing__live-badge">{t("media:widget.server_playing.live")}</span>
            {card.channel ? (
              <small>
                <Icon name="tv" size={12} />
                {card.channel}
              </small>
            ) : null}
          </span>
        ) : (
          <Progress card={card} />
        )}
      </span>
    </>
  );
  return card.route ? <Link to={card.route}>{body}</Link> : <span>{body}</span>;
}

/** Several sessions: each one in full, swiped sideways (two at a time on a wide block), dots saying which. */
function Sessions({ items }: { items: Playing[] }) {
  const t = useT();
  const track = useRef<HTMLUListElement>(null);
  const [shown, setShown] = useState(0);
  const onScroll = () => {
    const list = track.current;
    const first = list?.firstElementChild as HTMLElement | null;
    if (!list || !first) return;
    setShown(Math.round(list.scrollLeft / Math.max(1, first.offsetWidth)));
  };
  const go = (index: number) => {
    const list = track.current;
    const target = list?.children[index] as HTMLElement | undefined;
    if (list && target) list.scrollTo({ left: target.offsetLeft - list.offsetLeft, behavior: "smooth" });
  };
  return (
    <div className="widget-playing widget-playing--many">
      <ul ref={track} className="widget-playing__track" onScroll={onScroll} data-nofit>
        {items.map((card, index) => (
          // biome-ignore lint/suspicious/noArrayIndexKey: two sessions may play the same title
          <li key={`${card.id ?? card.title}-${index}`} data-mine={card.mine || undefined}>
            <PlayingCard card={card} hero />
          </li>
        ))}
      </ul>
      <span className="widget-playing__dots">
        {items.map((card, index) => (
          <button
            // biome-ignore lint/suspicious/noArrayIndexKey: one dot per session, in order
            key={`${card.id ?? card.title}-dot-${index}`}
            type="button"
            aria-label={t("media:widget.server_playing.show", { n: index + 1, title: card.title })}
            aria-current={index === shown || undefined}
            onClick={() => go(index)}
          />
        ))}
      </span>
    </div>
  );
}

/**
 * « Playing on the server » (027, #31): what runs now — titles, state and progress, never who (only the
 * viewer's own are marked). One session gets the whole block (poster, what it is, how long is left);
 * several are swiped through, a dot each (two at a time when wide); on a single row, how many and the
 * first one.
 */
function ServerPlaying({ payload, compact }: WidgetProps) {
  const t = useT();
  const data = (payload.data ?? {}) as { items?: Playing[]; count?: number; mine?: boolean };
  const items = data.items ?? [];
  const count = data.count ?? items.length;
  if (!items.length)
    return (
      <p className="widget-server-playing__none">
        <Icon name="moon" size={16} />
        {t(data.mine ? "media:widget.server_playing.none_mine" : "media:widget.server_playing.none")}
      </p>
    );
  const first = items[0] as Playing;
  const streams = (
    <span className="widget-server-playing__count">
      <span className="widget-server-playing__dot" aria-hidden="true" />
      {t("media:widget.server_playing.count", { count })}
    </span>
  );
  if (compact)
    return (
      <div className="widget-playing widget-playing--compact">
        {streams}
        <PlayingCard card={first} />
      </div>
    );
  return (
    <>
      <WidgetHeaderAction>{streams}</WidgetHeaderAction>
      {items.length === 1 ? (
        <div className="widget-playing widget-playing--one">
          <PlayingCard card={first} hero />
        </div>
      ) : (
        <Sessions items={items} />
      )}
    </>
  );
}

// --- a year ago ----------------------------------------------------------------------------------------------
interface Moment {
  years: number;
  date: string;
  watched: Card[];
  added: Card[];
}

function Shelf({ label, cards }: { label: string; cards: Card[] }) {
  if (!cards.length) return null;
  return (
    <section className="widget-on-this-day__shelf">
      <h4>
        {label} <small>{cards.length}</small>
      </h4>
      <ul data-nofit>
        {cards.map((card, index) => {
          const src = art(card);
          const body = (
            <>
              <span className="widget-on-this-day__photo">
                {src ? (
                  <img src={src} alt="" loading="lazy" />
                ) : (
                  <Icon name={KIND_ICON[card.kind ?? ""] ?? "film"} size={22} />
                )}
              </span>
              <span className="widget-on-this-day__caption">{card.title}</span>
            </>
          );
          return (
            <li
              // biome-ignore lint/suspicious/noArrayIndexKey: a title may come back twice
              key={`${card.id ?? card.title}-${index}`}
              style={{ "--tilt": `${((index * 7) % 5) - 2}deg` } as CSSProperties}
              title={card.subtitle ? `${card.title} · ${card.subtitle}` : card.title}
            >
              {card.route ? <Link to={card.route}>{body}</Link> : <span>{body}</span>}
            </li>
          );
        })}
      </ul>
    </section>
  );
}

/**
 * « A year ago » (027, #31): around this date one, two… five years back — what I watched then and what
 * came into the library — one year at a time, picked with chips (the nearest first, turning on its own
 * until one is picked); on a single row, the nearest year in a sentence.
 */
function OnThisDay({ payload, compact }: WidgetProps) {
  const t = useT();
  const format = useFormat();
  const ref = useRef<HTMLDivElement>(null);
  const lively = useLively(ref);
  const moments = ((payload.data ?? {}) as { moments?: Moment[] }).moments ?? [];
  const [index, setIndex] = useState(0);
  const [picked, setPicked] = useState(false);
  useEffect(() => {
    if (!lively || picked || moments.length < 2) return;
    const timer = window.setInterval(() => setIndex((n) => (n + 1) % moments.length), 9000);
    return () => window.clearInterval(timer);
  }, [lively, picked, moments.length]);
  if (!moments.length)
    return (
      <p className="widget-on-this-day__none">
        <Icon name="hourglass" size={16} />
        {t("media:widget.on_this_day.none")}
      </p>
    );
  const moment = moments[index % moments.length] as Moment;
  const when = t("media:widget.on_this_day.when", {
    years: moment.years,
    date: format.date(`${moment.date}T12:00:00`, "medium"),
  });
  if (compact) {
    const first = moment.watched[0] ?? moment.added[0];
    return (
      <div ref={ref} className="widget-on-this-day widget-on-this-day--compact">
        <Icon name="hourglass" size={14} />
        <span>
          <strong>{when}</strong>
          {first ? ` · ${first.title}` : ""}
          {moment.added.length
            ? ` · ${t("media:widget.on_this_day.arrivals", { count: moment.added.length })}`
            : ""}
        </span>
      </div>
    );
  }
  return (
    <div ref={ref} className="widget-on-this-day">
      <div className="widget-on-this-day__head">
        <span className="widget-on-this-day__when">
          <Icon name="hourglass" size={14} />
          {when}
        </span>
        {moments.length > 1 ? (
          <span className="widget-on-this-day__years">
            {moments.map((m, i) => (
              <button
                key={m.years}
                type="button"
                aria-pressed={i === index % moments.length}
                onClick={() => {
                  setIndex(i);
                  setPicked(true);
                }}
              >
                {t("media:widget.on_this_day.chip", { years: m.years })}
              </button>
            ))}
          </span>
        ) : null}
      </div>
      <div className="widget-on-this-day__shelves" key={moment.years}>
        <Shelf label={t("media:widget.on_this_day.watched")} cards={moment.watched} />
        <Shelf label={t("media:widget.on_this_day.added")} cards={moment.added} />
      </div>
    </div>
  );
}

// --- next releases ---------------------------------------------------------------------------------------------
interface Release extends Card {
  at: string;
  year?: number | null;
  genres?: string[] | null;
  rating?: number | null;
  overview?: string | null;
  reason?: "requested" | "watching";
  type?: string;
  season?: number | null;
  episode?: number | null;
}
const RELEASE_TYPES = new Set(["air", "cinema", "digital", "physical", "release"]);

function useTick(lively: boolean): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (!lively) return;
    setNow(Date.now());
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, [lively]);
  return now;
}

function Unit({ value, of, label }: { value: number; of: number; label: string }) {
  return (
    <span className="widget-next__unit" style={{ "--part": Math.min(1, value / of) } as CSSProperties}>
      <strong>{String(value).padStart(2, "0")}</strong>
      <small>{label}</small>
    </span>
  );
}

function episodeOf(release: Release): string | null {
  if (release.season === null || release.season === undefined) return null;
  const pad = (n: number | null | undefined) => String(n ?? 0).padStart(2, "0");
  return `S${pad(release.season)}E${pad(release.episode)}`;
}

/** « Next releases » (027): the soonest of what I asked for or follow, counting down to the second; the
 * others below — picking one brings it forward. */
function NextReleases({ payload, compact }: WidgetProps) {
  const t = useT();
  const format = useFormat();
  const ref = useRef<HTMLDivElement>(null);
  const lively = useLively(ref);
  const now = useTick(lively);
  const [chosen, setChosen] = useState(0);
  const items = (((payload.data ?? {}) as { items?: Release[] }).items ?? []).filter((r) => r.at);
  if (!items.length)
    return (
      <p className="widget-server-playing__none">
        <Icon name="rocket" size={16} />
        {t("media:widget.next_releases.none")}
      </p>
    );
  const hero = items[Math.min(chosen, items.length - 1)] as Release;
  const left = Math.max(0, Date.parse(hero.at) - now);
  const days = Math.floor(left / 86_400_000);
  const hours = Math.floor((left % 86_400_000) / 3_600_000);
  const minutes = Math.floor((left % 3_600_000) / 60_000);
  const seconds = Math.floor((left % 60_000) / 1000);
  const src = art(hero);
  if (compact)
    // 027: on a single row — the soonest, and how long until it is out
    return (
      <div ref={ref} className="widget-next--compact">
        <Link to={hero.route ?? "/media"}>
          <span className="widget-next__mini">{src ? <img src={src} alt="" /> : null}</span>
          <span className="widget-next__mini-text">
            <span>{hero.title}</span>
            <small>
              {episodeOf(hero) ??
                (hero.type && RELEASE_TYPES.has(hero.type) ? t(`media:widget.release.${hero.type}`) : "")}
            </small>
          </span>
          <span className="widget-next__inline" role="timer">
            {left > 0
              ? `${days}${t("media:widget.next_releases.d")} ${String(hours).padStart(2, "0")}:${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`
              : t("media:widget.next_releases.out")}
          </span>
        </Link>
      </div>
    );
  const details = [
    episodeOf(hero),
    hero.subtitle,
    hero.type && RELEASE_TYPES.has(hero.type) ? t(`media:widget.release.${hero.type}`) : null,
    // a date without its time (a film's release) says the day only
    /T00:00(:00)?([.+Z]|$)/.test(hero.at)
      ? format.date(`${hero.at.slice(0, 10)}T12:00:00`, "medium")
      : format.dateTime(new Date(hero.at)),
  ].filter(Boolean);
  return (
    <div ref={ref} className="widget-next">
      <Link className="widget-next__hero" to={hero.route ?? "/media"} key={hero.id ?? hero.title}>
        <span className="widget-next__poster">
          {src ? <img src={src} alt="" /> : <Icon name={KIND_ICON[hero.kind ?? ""] ?? "film"} size={26} />}
        </span>
        <span className="widget-next__info">
          {hero.reason ? (
            <span className="widget-next__reason" data-reason={hero.reason}>
              <Icon name={hero.reason === "requested" ? "inbox" : "eye"} size={12} />
              {t(`media:widget.next_releases.reason.${hero.reason}`)}
            </span>
          ) : null}
          <strong className="widget-next__title">{hero.title}</strong>
          <small className="widget-next__details">{details.join(" · ")}</small>
          <TitleFacts facts={hero} />
        </span>
        {left > 0 ? (
          <span
            className="widget-next__count"
            role="timer"
            aria-label={t("media:widget.next_releases.left", { days, hours, minutes })}
          >
            <Unit value={days} of={30} label={t("media:widget.next_releases.days")} />
            <Unit value={hours} of={24} label={t("media:widget.next_releases.hours")} />
            <Unit value={minutes} of={60} label={t("media:widget.next_releases.minutes")} />
            <Unit value={seconds} of={60} label={t("media:widget.next_releases.seconds")} />
          </span>
        ) : (
          <span className="widget-next__out">{t("media:widget.next_releases.out")}</span>
        )}
      </Link>
      {items.length > 1 ? (
        <ul className="widget-next__more">
          {items.map((release, index) =>
            index === chosen ? null : (
              // biome-ignore lint/suspicious/noArrayIndexKey: a title comes once, its index is stable
              <li key={`${release.id ?? release.title}-${index}`}>
                <button type="button" onClick={() => setChosen(index)} title={release.title}>
                  <span className="widget-next__mini">
                    {art(release) ? <img src={art(release) ?? ""} alt="" loading="lazy" /> : null}
                  </span>
                  <span className="widget-next__mini-text">
                    <span>{release.title}</span>
                    <small>{format.relative((Date.parse(release.at) - now) / 1000)}</small>
                  </span>
                </button>
              </li>
            ),
          )}
        </ul>
      ) : null}
    </div>
  );
}

registerWidgetComponent("media.next_releases", NextReleases);
registerWidgetComponent("media.living_wall", LivingWall);
registerWidgetComponent("media.server_playing", ServerPlaying);
registerWidgetComponent("media.on_this_day", OnThisDay);
