import { Link } from "react-router";
import { Icon } from "../../../design-system/components/Icon";
import { useFormat } from "../../../i18n/format/useFormat";
import { useT } from "../../../i18n/hooks/useT";
import { metadataImage } from "../../media/detail/Enrichment";
import { registerWidgetComponent, type WidgetProps } from "./registry";
import "./downloads.css";

interface LeavingCard {
  id: string;
  title: string;
  kind: string;
  delete_at: string | null;
  collection: string;
  image_id: string | null;
  poster_ref?: string | null;
  route: string | null;
}

const art = (card: LeavingCard): string | null =>
  card.image_id ? `/api/v1/media/images/${card.image_id}` : metadataImage(card.poster_ref, "w342");

/**
 * « Leaving soon » (#57): the posters of what the library's cleanup will delete, the first to go first,
 * each with its day — a title's page saves it (with a rescue from the shop).
 */
function Leaving({ payload, compact }: WidgetProps) {
  const t = useT();
  const format = useFormat();
  const items = ((payload.data ?? {}) as { items?: LeavingCard[] }).items ?? [];
  if (!items.length) return <p className="widget-empty">{t("media:widget.leaving.empty")}</p>;
  return (
    <ul className="widget-leaving" data-compact={compact || undefined} data-nofit>
      {(compact ? items.slice(0, 3) : items).map((card) => {
        const src = art(card);
        const when = card.delete_at
          ? t("media:widget.leaving.on", {
              when: format.relative((Date.parse(card.delete_at) - Date.now()) / 1000),
            })
          : t("media:widget.leaving.someday");
        const body = (
          <>
            <span className="widget-leaving__poster">
              {src ? (
                <img src={src} alt="" loading="lazy" />
              ) : (
                <span className="widget-leaving__title">{card.title}</span>
              )}
              <span className="widget-leaving__when">
                <Icon name="trash" size={11} />
                {when}
              </span>
            </span>
            <span className="visually-hidden">{card.title}</span>
          </>
        );
        return (
          <li key={card.id} title={`${card.title} — ${when}`}>
            {card.route ? <Link to={card.route}>{body}</Link> : body}
          </li>
        );
      })}
    </ul>
  );
}

registerWidgetComponent("media.leaving", Leaving);
