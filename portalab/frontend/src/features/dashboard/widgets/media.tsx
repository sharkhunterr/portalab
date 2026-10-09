import { lazy, Suspense, useEffect, useLayoutEffect, useRef, useState } from "react";
import { Link } from "react-router";
import { Icon } from "../../../design-system/components/Icon";
import { useFormat } from "../../../i18n/format/useFormat";
import { useT } from "../../../i18n/hooks/useT";
import { metadataImage } from "../../media/detail/Enrichment";
import { useMeasures } from "../../media/insights/api";
import type { SoonCard } from "../../media/requests/api";
import { SoonList } from "../../media/requests/SoonList";
import type { StatsPoint } from "./MediaStatsChart";
import { registerWidgetComponent, type WidgetProps } from "./registry";

/**
 * Media widgets (027): my statistics (time, plays, trend, a sparkline and my top titles) and a row of
 * posters shared by « recently added », « recently requested », « upcoming releases » and « top of the week ».
 */
interface Card {
  id: string | null;
  title: string;
  subtitle?: string | null;
  kind?: string;
  meta?: string | null;
  state?: string;
  at?: string;
  type?: string;
  season?: number | null;
  episode?: number | null;
  plays?: number;
  seconds?: number;
  image_id: string | null;
  /** 027: the metadata provider's poster when the library has none (requests, upcoming releases). */
  poster_ref?: string | null;
  route: string | null;
}

function poster(id: string | null): string | null {
  return id ? `/api/v1/media/images/${id}` : null;
}

function Posters({ payload }: WidgetProps) {
  const t = useT();
  const format = useFormat();
  const measures = useMeasures();
  const data = (payload.data ?? {}) as { items?: Card[]; mode?: "added" | "released" };
  const items = data.items ?? [];
  const caption = (card: Card) => {
    if (card.state) return t(`media:requests.state.${card.state}`);
    if (data.mode && card.at) {
      // 027: « added 2 days ago » / « out on 3 Oct. », with the new episode of a series
      const when =
        data.mode === "added"
          ? format.relative((Date.parse(card.at) - Date.now()) / 1000)
          : format.date(`${card.at.slice(0, 10)}T12:00:00Z`, "medium");
      return card.meta && /^S\d+E\d+$/.test(card.meta) ? `${card.meta} · ${when}` : when;
    }
    if (card.type && card.at) {
      const when = format.date(card.at, "medium");
      const episode =
        card.season !== null &&
        card.season !== undefined &&
        card.episode !== null &&
        card.episode !== undefined
          ? `S${String(card.season).padStart(2, "0")}E${String(card.episode).padStart(2, "0")} · `
          : "";
      return `${episode}${t(`media:widget.release.${card.type}`)} · ${when}`;
    }
    if (card.seconds)
      return `${measures.duration(card.seconds)} · ${t("media:insights.plays", { count: card.plays ?? 0 })}`;
    return card.meta ?? (card.kind ? t(`media:kind.${card.kind}`) : "");
  };
  return (
    <ul className="widget-posters">
      {items.map((card, index) => {
        const src = poster(card.image_id) ?? metadataImage(card.poster_ref, "w342");
        const body = (
          <>
            <span className="widget-posters__art">
              {src ? <img src={src} alt="" loading="lazy" /> : <Icon name="film" size={24} />}
              {card.state ? <span className="widget-posters__badge" data-request={card.state} /> : null}
            </span>
            <span className="widget-posters__title">{card.title}</span>
            {card.subtitle ? <span className="widget-posters__meta">{card.subtitle}</span> : null}
            <span className="widget-posters__meta">{caption(card)}</span>
          </>
        );
        return (
          // biome-ignore lint/suspicious/noArrayIndexKey: releases of one title may share their id
          <li key={`${card.id ?? card.title}-${index}`}>
            {card.route ? <Link to={card.route}>{body}</Link> : <span>{body}</span>}
          </li>
        );
      })}
    </ul>
  );
}

/**
 * « Poster wall » (027, sold in the shop): the month's most watched titles as a dense wall of posters, the
 * plays on each, the first ones larger — it fills its block, and opens each title.
 */
function PosterWall({ payload }: WidgetProps) {
  const t = useT();
  const items = ((payload.data ?? {}) as { items?: Card[] }).items ?? [];
  return (
    <ul className="widget-wall">
      {items.map((card, index) => {
        const src = poster(card.image_id) ?? metadataImage(card.poster_ref, "w342");
        const body = (
          <>
            {src ? (
              <img src={src} alt="" loading="lazy" />
            ) : (
              <span className="widget-wall__title">{card.title}</span>
            )}
            {card.plays ? (
              <span className="widget-wall__plays">
                <Icon name="play" size={10} />
                {t("media:insights.plays", { count: card.plays })}
              </span>
            ) : null}
          </>
        );
        return (
          <li
            // biome-ignore lint/suspicious/noArrayIndexKey: a title may appear once per kind
            key={`${card.id ?? card.title}-${index}`}
            data-rank={index < 2 ? "top" : undefined}
            title={card.title}
          >
            {card.route ? <Link to={card.route}>{body}</Link> : <span>{body}</span>}
          </li>
        );
      })}
    </ul>
  );
}

const KIND_ICON: Record<string, string> = {
  movie: "film",
  episode: "tv",
  book: "book",
  audiobook: "headphones",
  track: "music",
};

/** « Continue » (027): what I am in the middle of — poster, title, episode or author, a progress bar. */
function Continue({ payload }: WidgetProps) {
  const t = useT();
  const items = ((payload.data ?? {}) as { items?: Array<Card & { progress?: number | null }> }).items ?? [];
  return (
    <ul className="widget-continue">
      {items.map((card, index) => {
        const src = poster(card.image_id) ?? metadataImage(card.poster_ref, "w342");
        const percent =
          card.progress !== null && card.progress !== undefined ? Math.round(card.progress * 100) : null;
        const body = (
          <>
            <span className="widget-continue__art">
              {src ? (
                <img src={src} alt="" loading="lazy" />
              ) : (
                <Icon name={KIND_ICON[card.kind ?? ""] ?? "film"} size={26} />
              )}
              <span className="widget-continue__kind" aria-hidden="true">
                <Icon name={KIND_ICON[card.kind ?? ""] ?? "film"} size={12} />
              </span>
            </span>
            <span className="widget-continue__text">
              <span className="widget-continue__title">{card.title}</span>
              {card.subtitle ? <span className="widget-continue__meta">{card.subtitle}</span> : null}
              {percent !== null ? (
                <span
                  className="widget-continue__bar"
                  role="progressbar"
                  aria-valuenow={percent}
                  aria-valuemin={0}
                  aria-valuemax={100}
                  aria-label={card.title}
                >
                  <span style={{ inlineSize: `${percent}%` }} />
                </span>
              ) : card.subtitle ? null : (
                // the kind only when nothing else says what it is (an episode has its « S02E11 »)
                <span className="widget-continue__meta">{t(`media:kind.${card.kind ?? "movie"}`)}</span>
              )}
            </span>
          </>
        );
        return (
          // biome-ignore lint/suspicious/noArrayIndexKey: two sessions may share a title
          <li key={`${card.id ?? card.title}-${index}`}>
            {card.route ? <Link to={card.route}>{body}</Link> : <span>{body}</span>}
          </li>
        );
      })}
    </ul>
  );
}

interface StatsData {
  scope: "me" | "all";
  period: string;
  category: string;
  metric: "time" | "plays";
  chart: "bars" | "area" | "donut" | "top" | "figures";
  unit: string;
  totals: { plays: number; seconds: number; works: number; completed: number };
  previous: { plays: number; seconds: number } | null;
  by_kind: Array<{ kind: string; seconds: number; plays: number }>;
  timeline: StatsPoint[];
  top: Card[];
}

const MediaStatsChart = lazy(() => import("./MediaStatsChart"));

/** « My statistics » (027): configurable — whose, period, category, metric and chart. */
function Stats({ payload }: WidgetProps) {
  const t = useT();
  const format = useFormat();
  const measures = useMeasures();
  const data = (payload.data ?? {}) as unknown as StatsData;
  const metric = data.metric ?? "time";
  const chart = data.chart ?? "bars";
  const headline =
    metric === "time" ? measures.duration(data.totals.seconds) : format.number(data.totals.plays);
  const before = data.previous ? (metric === "time" ? data.previous.seconds : data.previous.plays) : 0;
  const now = metric === "time" ? data.totals.seconds : data.totals.plays;
  const trend = before ? (now - before) / before : null;
  const context = [
    t(`media:insights.scope.${data.scope ?? "me"}`),
    t(`media:insights.periods.${data.period ?? "30d"}`),
    data.category && data.category !== "all" ? t(`media:insights.categories.${data.category}`) : null,
  ]
    .filter(Boolean)
    .join(" · ");
  return (
    <div className="widget-media-stats">
      <p className="widget-media-stats__context">{context}</p>
      <div className="widget-media-stats__figures">
        <p>
          <strong>{headline}</strong>
          <span>{t(metric === "time" ? "media:insights.stat.time" : "media:insights.stat.plays")}</span>
        </p>
        <p>
          <strong>
            {metric === "time" ? format.number(data.totals.plays) : measures.duration(data.totals.seconds)}
          </strong>
          <span>{t(metric === "time" ? "media:insights.stat.plays" : "media:insights.stat.time")}</span>
        </p>
        <p>
          <strong>{format.number(data.totals.works)}</strong>
          <span>{t("media:insights.stat.works")}</span>
        </p>
        {trend !== null ? (
          <p data-trend={trend >= 0 ? "up" : "down"}>
            <strong>
              <Icon name={trend >= 0 ? "arrow-up" : "arrow-down"} size={16} />
              {format.percent(Math.abs(trend))}
            </strong>
            <span>{t("media:widget.stats.trend")}</span>
          </p>
        ) : null}
      </div>
      {chart === "bars" || chart === "area" || chart === "donut" ? (
        <Suspense fallback={<div className="widget-media-stats__placeholder" />}>
          <MediaStatsChart
            chart={chart}
            metric={metric}
            unit={data.unit ?? "day"}
            timeline={data.timeline ?? []}
            byKind={data.by_kind ?? []}
          />
        </Suspense>
      ) : null}
      {chart === "top" && data.top?.length ? (
        <ol className="widget-rows">
          {data.top.map((card) => {
            const src = poster(card.image_id);
            const body = (
              <>
                <span className="widget-row__thumb widget-row__thumb--poster">
                  {src ? <img src={src} alt="" loading="lazy" /> : <Icon name="film" size={18} />}
                </span>
                <span className="widget-row__main">
                  <span className="widget-row__title">{card.title}</span>
                  <span className="widget-row__meta">
                    {measures.duration(card.seconds ?? 0)} ·{" "}
                    {t("media:insights.plays", { count: card.plays ?? 0 })}
                  </span>
                </span>
              </>
            );
            return (
              <li key={card.id ?? card.title} className="widget-row">
                {card.route ? <Link to={card.route}>{body}</Link> : <span>{body}</span>}
              </li>
            );
          })}
        </ol>
      ) : null}
      <Link
        to={`/media/insights${data.scope === "all" ? "?scope=all" : ""}`}
        className="widget-media-stats__more"
      >
        {t("media:widget.stats.more")}
      </Link>
    </div>
  );
}

/** « Coming soon » (027): my requests downloading, importing or with a release date. */
function Soon({ payload }: WidgetProps) {
  const items = ((payload.data ?? {}) as { items?: SoonCard[] }).items ?? [];
  return <SoonList items={items} compact />;
}

registerWidgetComponent("media.posters", Posters);
registerWidgetComponent("media.wall", PosterWall);
registerWidgetComponent("media.soon", Soon);
const MAX_LINES = 4;

interface ShuffleCard extends Card {
  year?: number | null;
  genres?: string[];
  overview?: string | null;
}

/**
 * « Shuffle » (027, #12): a title drawn at random from the library — the media home's « what are we
 * watching » banner, its posters scrolling behind as a frieze. « Another one » draws again among the batch
 * (never the same twice in a row); the picked poster stands in front when the block is large enough.
 */
function Shuffle({ payload }: WidgetProps) {
  const t = useT();
  const items = ((payload.data ?? {}) as { items?: ShuffleCard[] }).items ?? [];
  const [index, setIndex] = useState(() => Math.floor(Math.random() * Math.max(1, items.length)));
  const pick = items[index % Math.max(1, items.length)];
  // #26: the overview gives up lines (4 → 0), then the title keeps one, until everything fits the block
  const box = useRef<HTMLDivElement>(null);
  const [lines, setLines] = useState(MAX_LINES);
  const [measure, setMeasure] = useState(0);
  useEffect(() => {
    const element = box.current;
    if (!element || typeof ResizeObserver === "undefined") return;
    const again = new ResizeObserver(() => setMeasure((n) => n + 1));
    again.observe(element);
    return () => again.disconnect();
  }, []);
  // a new title or a new size starts the fitting over (a new round, from the most lines)
  const [round, setRound] = useState(0);
  const pickId = pick?.id ?? null;
  useLayoutEffect(() => {
    if (pickId === undefined) return;
    void measure;
    setLines(MAX_LINES);
    setRound((n) => n + 1);
  }, [pickId, measure]);
  useLayoutEffect(() => {
    void round;
    const element = box.current;
    const text = element?.querySelector<HTMLElement>(".widget-shuffle__text");
    if (!element || !text) return;
    const style = getComputedStyle(element);
    const room =
      element.clientHeight - Number.parseFloat(style.paddingTop) - Number.parseFloat(style.paddingBottom);
    if (text.scrollHeight > room + 1 && lines > -1) setLines((n) => n - 1);
  }, [lines, round]);
  if (!pick) return <p className="widget-empty">{t("media:widget.shuffle.empty")}</p>;
  const another = () =>
    setIndex((current) => {
      if (items.length < 2) return current;
      let next = current;
      while (next === current) next = Math.floor(Math.random() * items.length);
      return next;
    });
  const frieze = items.map((card) => poster(card.image_id)).filter((src): src is string => Boolean(src));
  const meta = [
    pick.year ? String(pick.year) : null,
    pick.kind ? t(`media:kind.${pick.kind}`) : null,
    ...(pick.genres ?? []),
  ]
    .filter(Boolean)
    .join(" · ");
  const art = poster(pick.image_id);
  return (
    <div
      ref={box}
      className="widget-shuffle"
      data-nofit
      data-tight={lines < 0 || undefined}
      style={{ "--overview-lines": Math.max(lines, 0) } as React.CSSProperties}
    >
      <span className="widget-shuffle__frieze" aria-hidden="true">
        <span className="widget-shuffle__track">
          {[...frieze, ...frieze].map((src, i) => (
            // biome-ignore lint/suspicious/noArrayIndexKey: the frieze repeats itself to loop seamlessly
            <img key={`${src}-${i}`} src={src} alt="" loading="lazy" />
          ))}
        </span>
      </span>
      <div className="widget-shuffle__text" key={pick.id ?? pick.title}>
        <span className="widget-shuffle__eyebrow">
          <Icon name="shuffle" size={14} />
          {t("media:widget.shuffle.eyebrow")}
        </span>
        <strong className="widget-shuffle__title">{pick.title}</strong>
        {meta ? <span className="widget-shuffle__meta">{meta}</span> : null}
        {pick.overview && lines > 0 ? <p className="widget-shuffle__overview">{pick.overview}</p> : null}
        <span className="widget-shuffle__actions">
          {pick.route ? (
            <Link className="ds-button ds-button--primary" to={pick.route}>
              <Icon name="play" size={16} />
              {t("media:widget.shuffle.open")}
            </Link>
          ) : null}
          <button
            type="button"
            className="ds-button ds-button--secondary"
            onClick={another}
            disabled={items.length < 2}
          >
            <Icon name="shuffle" size={16} />
            {t("media:widget.shuffle.another")}
          </button>
        </span>
      </div>
      {art ? <img className="widget-shuffle__poster" key={art} src={art} alt="" /> : null}
    </div>
  );
}

registerWidgetComponent("media.shuffle", Shuffle);
registerWidgetComponent("media.continue", Continue);
registerWidgetComponent("media.stats", Stats);
