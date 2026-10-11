import { Link } from "react-router";
import { Icon } from "../../../design-system/components/Icon";
import { useFormat } from "../../../i18n/format/useFormat";
import { useT } from "../../../i18n/hooks/useT";
import { metadataImage } from "../../media/detail/Enrichment";
import { useMeasures } from "../../media/insights/api";
import { WidgetHeaderAction } from "../frame/actions";
import { registerWidgetComponent, type WidgetProps } from "./registry";
import "./downloads.css";

/** One title being downloaded (a series' episodes together), as the server sends it (#58). */
interface Download {
  id: string | null;
  title: string;
  kind: "movie" | "series";
  state: "downloading" | "importing" | "stalled" | "queued" | "paused" | "warning";
  progress: number;
  speed: number;
  upload_speed: number;
  eta_s: number | null;
  seeds: number | null;
  peers: number | null;
  size: number | null;
  count: number;
  client: string | null;
  episode?: { season: number; episode: number | null; title: string };
  image_id: string | null;
  poster_ref?: string | null;
  route: string | null;
}

const STATE_ICON: Record<Download["state"], string> = {
  downloading: "download",
  importing: "library",
  stalled: "warning",
  queued: "hourglass",
  paused: "pause",
  warning: "alert",
};

const art = (item: Download): string | null =>
  item.image_id ? `/api/v1/media/images/${item.image_id}` : metadataImage(item.poster_ref, "w185");

function Row({ item }: { item: Download }) {
  const t = useT();
  const format = useFormat();
  const measures = useMeasures();
  const percent = Math.round(item.progress * 100);
  const size = (bytes: number) => measures.bytes(bytes);
  const src = art(item);
  const subtitle = item.episode
    ? `S${String(item.episode.season).padStart(2, "0")}E${String(item.episode.episode ?? 0).padStart(2, "0")} · ${item.episode.title}`
    : item.kind === "series"
      ? t("media:widget.downloads.episodes", { count: item.count })
      : null;
  const facts = [
    format.percent(percent / 100),
    item.speed ? `${size(item.speed)}/s` : null,
    item.eta_s ? t("media:widget.downloads.left", { time: measures.duration(item.eta_s) }) : null,
    item.seeds !== null && item.peers !== null
      ? t("media:widget.downloads.peers", { seeds: item.seeds, peers: item.peers })
      : null,
    item.size ? size(item.size) : null,
  ].filter(Boolean);
  const body = (
    <>
      <span className="widget-downloads__poster">
        {src ? (
          <img src={src} alt="" loading="lazy" />
        ) : (
          <Icon name={item.kind === "series" ? "tv" : "film"} size={18} />
        )}
      </span>
      <span className="widget-downloads__info">
        <span className="widget-downloads__head">
          <strong>{item.title}</strong>
          <span className="widget-downloads__state" data-phase={item.state}>
            <Icon name={STATE_ICON[item.state] ?? "download"} size={11} />
            {t(`media:widget.downloads.state.${item.state}`)}
          </span>
        </span>
        {subtitle ? <small className="widget-downloads__subtitle">{subtitle}</small> : null}
        <span
          className="widget-downloads__bar"
          data-phase={item.state}
          role="progressbar"
          aria-valuenow={percent}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-label={item.title}
        >
          <span style={{ inlineSize: `${percent}%` }} />
        </span>
        <small className="widget-downloads__facts">{facts.join(" · ")}</small>
      </span>
    </>
  );
  return <li>{item.route ? <Link to={item.route}>{body}</Link> : <span>{body}</span>}</li>;
}

/**
 * « Downloads in progress » (#58): each title the download managers fetch or import — poster, state,
 * progress, speed, time left and peers (the torrent clients'), a series' episodes together; the titles,
 * never who asked. One row: how many and the first one.
 */
function Downloads({ payload, compact }: WidgetProps) {
  const t = useT();
  const measures = useMeasures();
  const data = (payload.data ?? {}) as { items?: Download[]; count?: number; speed?: number; mine?: boolean };
  const items = data.items ?? [];
  if (!items.length)
    return (
      <p className="widget-downloads__none">
        <Icon name="check" size={16} />
        {t(data.mine ? "media:widget.downloads.none_mine" : "media:widget.downloads.none")}
      </p>
    );
  const total = (
    <span className="widget-downloads__total">
      {t("media:widget.downloads.count", { count: data.count ?? items.length })}
      {data.speed ? ` · ${measures.bytes(data.speed)}/s` : ""}
    </span>
  );
  return (
    <>
      {compact ? null : <WidgetHeaderAction>{total}</WidgetHeaderAction>}
      <ul className="widget-downloads" data-compact={compact || undefined} data-nofit>
        {(compact ? items.slice(0, 1) : items).map((item) => (
          <Row key={`${item.kind}-${item.id ?? item.title}`} item={item} />
        ))}
      </ul>
    </>
  );
}

registerWidgetComponent("media.downloads", Downloads);
