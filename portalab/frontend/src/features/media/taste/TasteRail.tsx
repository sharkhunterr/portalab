import { Link } from "react-router";
import { Icon } from "../../../design-system/components/Icon";
import { useFormat } from "../../../i18n/format/useFormat";
import { useT } from "../../../i18n/hooks/useT";
import { imageUrl } from "../api";
import { KIND_ICONS, Poster } from "../MediaGrid";
import type { TasteCard } from "./api";
import { reasonOf } from "./reason";
import "./taste.css";

/** Issue 190: titles of my taste in a row — each poster with why it is here (« Saga Hunger Games »). */
export function TasteRail({ items, label, grid }: { items: TasteCard[]; label: string; grid?: boolean }) {
  const t = useT();
  const format = useFormat();
  return (
    <ul className={grid ? "media-grid" : "media-rail"} aria-label={label}>
      {items.map((card) => {
        const why = reasonOf(card.reason, t, format.list);
        return (
          <li key={card.id} className="media-card" data-available={card.available}>
            <Link to={`/media/${card.id}`} className="media-card__link" title={why?.like ?? undefined}>
              <span className="media-card__frame">
                <Poster src={imageUrl(card.image_id)} kind={card.kind} />
                <span className="media-card__kind" title={t(`media:kind.${card.kind}`)}>
                  <Icon name={KIND_ICONS[card.kind] ?? "film"} size={12} />
                </span>
              </span>
              <span className="media-card__title">{card.title}</span>
            </Link>
            {why ? (
              <span className="media-card__reason">
                <Icon name="sparkles" size={12} />
                <span>{why.short}</span>
              </span>
            ) : null}
            <span className="media-card__meta">
              {t(`media:kind.${card.kind}`)}
              {card.year ? ` · ${card.year}` : ""}
            </span>
          </li>
        );
      })}
    </ul>
  );
}
