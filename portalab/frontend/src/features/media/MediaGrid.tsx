import { type ReactNode, useState } from "react";
import { Link } from "react-router";
import { Icon } from "../../design-system/components/Icon";
import { useT } from "../../i18n/hooks/useT";
import { PosterTickets } from "../support/tickets/MediaTickets";
import { imageUrl, type MediaCard } from "./api";
import { PosterBadge } from "./discover/StatusBadge";

export const KIND_ICONS: Record<string, string> = {
  movie: "film",
  series: "tv",
  season: "tv",
  episode: "tv",
  book: "book",
  audiobook: "headphones",
  game: "joystick",
  album: "music",
  track: "music",
  live: "radio",
  radio: "radio", // issue 283: the station's sittings in the statistics
};

/** A poster, or (no image) the kind's icon on a soft gradient — never an empty frame. */
export function Poster({ src, kind }: { src: string | null; kind: string }) {
  const [broken, setBroken] = useState(false);
  return src && !broken ? (
    <img src={src} alt="" loading="lazy" className="media-card__poster" onError={() => setBroken(true)} />
  ) : (
    <span className="media-card__poster media-card__poster--none" aria-hidden="true">
      <Icon name={KIND_ICONS[kind] ?? "film"} size={34} />
    </span>
  );
}

/** Media cards (027 redesign): the poster first, title and year under it; kind and availability as text
 * (never color alone). ``rail`` lays them in one scrolling row. */
export function MediaGrid({
  items,
  label,
  rail,
  note,
  badge,
}: {
  items: MediaCard[];
  label: string;
  rail?: boolean;
  /** 027: a line of its own under the title (when it was added or released, the new episode). */
  note?: ((item: MediaCard) => string | null) | undefined;
  /** issue 110: the badge on the poster instead of its standing (« leaving in 3 days ») */
  badge?: ((item: MediaCard) => ReactNode) | undefined;
}) {
  const t = useT();
  return (
    <ul className={rail ? "media-rail" : "media-grid"} aria-label={label}>
      {items.map((item) => (
        <li key={item.id} className="media-card" data-available={item.available}>
          <Link to={`/media/${item.id}`} className="media-card__link">
            <span className="media-card__frame">
              <Poster src={imageUrl(item.image_id)} kind={item.kind} />
              <PosterTickets mediaId={item.id} />
              {badge ? (
                badge(item)
              ) : (
                <PosterBadge status={item.available ? "available" : item.requested ? "requested" : null} />
              )}
            </span>
            <span className="media-card__title">{item.title}</span>
          </Link>
          {note?.(item) ? <span className="media-card__note">{note(item)}</span> : null}
          <span className="media-card__meta">
            {t(`media:kind.${item.kind}`)}
            {item.year ? ` · ${item.year}` : ""}
          </span>
        </li>
      ))}
    </ul>
  );
}
