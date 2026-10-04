import { Link } from "react-router";
import { Icon } from "../../../design-system/components/Icon";
import { useFormat } from "../../../i18n/format/useFormat";
import { useT } from "../../../i18n/hooks/useT";
import { useMeasures } from "../../media/insights/api";
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
  route: string | null;
}

function poster(id: string | null): string | null {
  return id ? `/api/v1/media/images/${id}` : null;
}

function Posters({ payload }: WidgetProps) {
  const t = useT();
  const format = useFormat();
  const measures = useMeasures();
  const items = ((payload.data ?? {}) as { items?: Card[] }).items ?? [];
  const caption = (card: Card) => {
    if (card.state) return t(`media:requests.state.${card.state}`);
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
        const src = poster(card.image_id);
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

interface StatsData {
  scope: "me" | "all";
  totals: { plays: number; seconds: number; works: number; completed: number };
  previous: { plays: number; seconds: number } | null;
  by_kind: Array<{ kind: string; seconds: number }>;
  timeline: Array<{ date: string; seconds: number }>;
  top: Card[];
}

function Stats({ payload }: WidgetProps) {
  const t = useT();
  const format = useFormat();
  const measures = useMeasures();
  const data = (payload.data ?? {}) as unknown as StatsData;
  const max = Math.max(1, ...(data.timeline ?? []).map((p) => p.seconds));
  const before = data.previous?.seconds ?? 0;
  const trend = before ? (data.totals.seconds - before) / before : null;
  return (
    <div className="widget-media-stats">
      <div className="widget-media-stats__figures">
        <p>
          <strong>{measures.duration(data.totals?.seconds ?? 0)}</strong>
          <span>{t("media:insights.stat.time")}</span>
        </p>
        <p>
          <strong>{format.number(data.totals?.plays ?? 0)}</strong>
          <span>{t("media:insights.stat.plays")}</span>
        </p>
        <p>
          <strong>{format.number(data.totals?.works ?? 0)}</strong>
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
      <div className="widget-media-stats__spark" aria-hidden="true">
        {(data.timeline ?? []).map((point) => (
          <span key={point.date} style={{ blockSize: `${Math.max(4, (point.seconds / max) * 100)}%` }} />
        ))}
      </div>
      {data.top?.length ? (
        <ol className="widget-media-stats__top">
          {data.top.map((card) => (
            <li key={card.id ?? card.title}>
              {card.route ? <Link to={card.route}>{card.title}</Link> : card.title}
            </li>
          ))}
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

registerWidgetComponent("media.posters", Posters);
registerWidgetComponent("media.stats", Stats);
