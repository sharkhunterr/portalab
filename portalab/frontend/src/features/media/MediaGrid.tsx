import { Link } from "react-router";
import { useT } from "../../i18n/hooks/useT";
import { imageUrl, type MediaCard } from "./api";

/** Media cards: poster (decorative, alt=""), title, year, kind and availability as text (never color alone). */
export function MediaGrid({ items, label }: { items: MediaCard[]; label: string }) {
  const t = useT();
  return (
    <ul className="media-grid" aria-label={label}>
      {items.map((item) => {
        const src = imageUrl(item.image_id);
        return (
          <li key={item.id} className="media-card" data-available={item.available}>
            {src ? <img src={src} alt="" loading="lazy" className="media-card__poster" /> : null}
            <Link to={`/media/${item.id}`} className="media-card__title">
              {item.title}
            </Link>
            <span className="media-card__meta">
              {t(`media:kind.${item.kind}`)}
              {item.year ? ` · ${item.year}` : ""} ·{" "}
              {item.available ? t("media:detail.available") : t("media:detail.unavailable")}
            </span>
          </li>
        );
      })}
    </ul>
  );
}
