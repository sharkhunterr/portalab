import { type CSSProperties, useEffect, useRef, useState } from "react";
import { Link } from "react-router";
import { Icon } from "../../../design-system/components/Icon";
import { useFormat } from "../../../i18n/format/useFormat";
import { useT } from "../../../i18n/hooks/useT";
import { metadataImage } from "../../media/detail/Enrichment";
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
const KIND_ICON: Record<string, string> = { movie: "film", episode: "tv", series: "tv", track: "music" };

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

function LivingWall({ payload }: WidgetProps) {
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
function ServerPlaying({ payload }: WidgetProps) {
  const t = useT();
  const data = (payload.data ?? {}) as { items?: Card[]; count?: number };
  const items = data.items ?? [];
  if (!items.length)
    return (
      <p className="widget-server-playing__none">
        <Icon name="moon" size={16} />
        {t("media:widget.server_playing.none")}
      </p>
    );
  return (
    <div className="widget-server-playing">
      <span className="widget-server-playing__count">
        <span className="widget-server-playing__dot" aria-hidden="true" />
        {t("media:widget.server_playing.count", { count: data.count ?? items.length })}
      </span>
      <ul>
        {items.map((card, index) => {
          const src = art(card);
          const percent =
            card.progress !== null && card.progress !== undefined ? Math.round(card.progress * 100) : null;
          const body = (
            <>
              <span className="widget-server-playing__art">
                {src ? (
                  <img src={src} alt="" loading="lazy" />
                ) : (
                  <Icon name={KIND_ICON[card.kind ?? ""] ?? "film"} size={20} />
                )}
              </span>
              <span className="widget-server-playing__text">
                <span className="widget-server-playing__title">
                  {card.title}
                  {card.mine ? (
                    <span className="widget-server-playing__you">{t("media:widget.server_playing.you")}</span>
                  ) : null}
                </span>
                {card.subtitle ? <span className="widget-server-playing__meta">{card.subtitle}</span> : null}
                <span className="widget-server-playing__state" data-playback={card.state}>
                  <Icon
                    name={
                      card.state === "paused" ? "pause" : card.state === "buffering" ? "hourglass" : "play"
                    }
                    size={11}
                  />
                  {card.state === "paused" || card.state === "buffering" ? (
                    <span>{t(`media:widget.server_playing.${card.state}`)}</span>
                  ) : null}
                  {percent !== null ? (
                    <span
                      className="widget-server-playing__bar"
                      role="progressbar"
                      aria-valuenow={percent}
                      aria-valuemin={0}
                      aria-valuemax={100}
                      aria-label={card.title}
                    >
                      <span style={{ inlineSize: `${percent}%` }} />
                    </span>
                  ) : null}
                </span>
              </span>
            </>
          );
          return (
            // biome-ignore lint/suspicious/noArrayIndexKey: two sessions may play the same title
            <li key={`${card.id ?? card.title}-${index}`} data-mine={card.mine || undefined}>
              {card.route ? <Link to={card.route}>{body}</Link> : <span>{body}</span>}
            </li>
          );
        })}
      </ul>
    </div>
  );
}

// --- a year ago ----------------------------------------------------------------------------------------------
function Stack({ label, cards }: { label: string; cards: Card[] }) {
  if (!cards.length) return null;
  return (
    <section className="widget-on-this-day__stack">
      <h4>{label}</h4>
      <ul>
        {cards.slice(0, 8).map((card, index) => {
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

function OnThisDay({ payload }: WidgetProps) {
  const t = useT();
  const format = useFormat();
  const data = (payload.data ?? {}) as {
    years?: number | null;
    date?: string;
    watched?: Card[];
    added?: Card[];
  };
  if (!data.years || !data.date)
    return (
      <p className="widget-on-this-day__none">
        <Icon name="hourglass" size={16} />
        {t("media:widget.on_this_day.none")}
      </p>
    );
  return (
    <div className="widget-on-this-day">
      <span className="widget-on-this-day__when">
        <Icon name="hourglass" size={14} />
        {t("media:widget.on_this_day.when", {
          years: data.years,
          date: format.date(`${data.date}T12:00:00`, "medium"),
        })}
      </span>
      <div className="widget-on-this-day__stacks">
        <Stack label={t("media:widget.on_this_day.watched")} cards={data.watched ?? []} />
        <Stack label={t("media:widget.on_this_day.added")} cards={data.added ?? []} />
      </div>
    </div>
  );
}

registerWidgetComponent("media.living_wall", LivingWall);
registerWidgetComponent("media.server_playing", ServerPlaying);
registerWidgetComponent("media.on_this_day", OnThisDay);
