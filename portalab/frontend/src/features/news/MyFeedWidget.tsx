import { type CSSProperties, useState } from "react";
import { Icon } from "../../design-system/components/Icon";
import { useFormat } from "../../i18n/format/useFormat";
import { useT } from "../../i18n/hooks/useT";
import { WidgetHeaderLink } from "../dashboard/frame/actions";
import { CompactLine } from "../dashboard/widgets/compact";
import { registerWidgetComponent, type WidgetProps } from "../dashboard/widgets/registry";
import { colorOf, SourceBadge } from "../media/feed/Timeline";
import { sourceIcon } from "./sourceKind";
import { PlayCover, YouTubePlayer, youtubeId } from "./YouTube";
import "./my-feed-widget.css";

interface Item {
  id: string;
  title: string;
  summary: string;
  link: string;
  source: string;
  source_kind: string;
  source_index: number;
  picture: string | null;
  published_at: string;
}

function Entry({ item }: { item: Item }) {
  const t = useT();
  const format = useFormat();
  const video = youtubeId(item.link);
  const [playing, setPlaying] = useState(false);
  const source = {
    key: item.source,
    label: item.source,
    icon: sourceIcon(item.source_kind),
    color: colorOf(item.source_index),
  };
  return (
    <li
      className="my-feed__item"
      data-playing={playing || undefined}
      style={{ "--badge": source.color } as CSSProperties}
    >
      {playing && video ? (
        <YouTubePlayer id={video} title={item.title} />
      ) : video ? (
        <PlayCover
          className="my-feed__picture"
          picture={item.picture}
          title={item.title}
          link={item.link}
          playing={false}
          onToggle={() => setPlaying(true)}
        />
      ) : (
        <span className="my-feed__picture" aria-hidden="true">
          {item.picture ? (
            <img src={item.picture} alt="" loading="lazy" />
          ) : (
            <Icon name={source.icon} size={22} />
          )}
        </span>
      )}
      <span className="my-feed__text">
        <span className="my-feed__meta">
          <SourceBadge source={source} />
          <span className="my-feed__when">
            {format.relative((Date.parse(item.published_at) - Date.now()) / 1000)}
          </span>
          {playing ? (
            <button
              type="button"
              className="my-feed__close"
              aria-label={t("news:video.close", { title: item.title })}
              onClick={() => setPlaying(false)}
            >
              <Icon name="close" size={14} />
            </button>
          ) : null}
        </span>
        <a href={item.link} target="_blank" rel="noopener noreferrer" className="my-feed__title">
          {item.title}
          <span className="visually-hidden">{t("news:external.opensSite")}</span>
        </a>
        {item.summary ? <span className="my-feed__summary">{item.summary}</span> : null}
      </span>
    </li>
  );
}

/**
 * Dashboard widget ``news.my_feed`` (issue 315): « Mon fil »'s latest news, each with its source's coloured
 * badge (as on the page). It takes the block's shape: on one row, the latest only; in a narrow column, rows
 * of a picture and a title; in a wide block, cards whose summary shows when there is room; as many as the
 * block holds, the rest counted. A YouTube video plays in place.
 */
function MyFeedWidget({ payload, compact }: WidgetProps) {
  const t = useT();
  const format = useFormat();
  const items = ((payload.data ?? {}) as { items?: Item[] }).items ?? [];
  const first = items[0];
  if (compact && first)
    return (
      <CompactLine
        to="/feed"
        image={first.picture}
        icon={sourceIcon(first.source_kind)}
        title={first.title}
        detail={`${first.source} · ${format.relative((Date.parse(first.published_at) - Date.now()) / 1000)}`}
      />
    );
  return (
    <>
      <WidgetHeaderLink to="/feed" label={t("news:widget.myFeed.all")} />
      <ul className="my-feed">
        {items.map((item) => (
          <Entry key={item.id} item={item} />
        ))}
      </ul>
    </>
  );
}

registerWidgetComponent("news.my_feed", MyFeedWidget);
