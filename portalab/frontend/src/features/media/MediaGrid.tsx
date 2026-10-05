import { useState } from "react";
import { Link } from "react-router";
import { Icon } from "../../design-system/components/Icon";
import { useT } from "../../i18n/hooks/useT";
import { imageUrl, type MediaCard } from "./api";

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
export function MediaGrid({ items, label, rail }: { items: MediaCard[]; label: string; rail?: boolean }) {
  const t = useT();
  return (
    <ul className={rail ? "media-rail" : "media-grid"} aria-label={label}>
      {items.map((item) => (
        <li key={item.id} className="media-card" data-available={item.available}>
          <Link to={`/media/${item.id}`} className="media-card__link">
            <span className="media-card__frame">
              <Poster src={imageUrl(item.image_id)} kind={item.kind} />
              {!item.available ? (
                <span className="media-card__flag" aria-hidden="true">
                  {t("media:detail.unavailable")}
                </span>
              ) : null}
            </span>
            <span className="media-card__title">{item.title}</span>
          </Link>
          <span className="media-card__meta">
            {t(`media:kind.${item.kind}`)}
            {item.year ? ` · ${item.year}` : ""} ·{" "}
            {item.available ? t("media:detail.available") : t("media:detail.unavailable")}
          </span>
        </li>
      ))}
    </ul>
  );
}
