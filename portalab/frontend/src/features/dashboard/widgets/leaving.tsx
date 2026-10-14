import { Link } from "react-router";
import { Icon } from "../../../design-system/components/Icon";
import { useFormat } from "../../../i18n/format/useFormat";
import { useT } from "../../../i18n/hooks/useT";
import { metadataImage } from "../../media/detail/Enrichment";
import { LeavingBadge } from "../../media/discover/StatusBadge";
import { PosterStrip } from "./compact";
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
 * each with its day — a title's page saves it (with a rescue from the shop). Issue 110: the same cards as
 * the other rows of posters (the poster, the title, its kind), the day as a badge on the poster like
 * « Available ».
 */
function Leaving({ payload, compact }: WidgetProps) {
  const t = useT();
  const format = useFormat();
  const items = ((payload.data ?? {}) as { items?: LeavingCard[] }).items ?? [];
  if (!items.length) return <p className="widget-empty">{t("media:widget.leaving.empty")}</p>;
  if (compact) {
    return (
      <PosterStrip
        cards={items.map((card) => ({ key: card.id, title: card.title, src: art(card), to: card.route }))}
      />
    );
  }
  return (
    <ul className="widget-posters">
      {items.map((card) => {
        const src = art(card);
        const when = card.delete_at
          ? t("media:widget.leaving.on", {
              when: format.relative((Date.parse(card.delete_at) - Date.now()) / 1000),
            })
          : t("media:widget.leaving.someday");
        const body = (
          <>
            <span className="widget-posters__art">
              {src ? <img src={src} alt="" loading="lazy" /> : <Icon name="film" size={24} />}
              {/* a small poster: the badge contracted to its icon, the sentence on hover */}
              <LeavingBadge label={when} title={when} />
            </span>
            <span className="widget-posters__title">{card.title}</span>
            <span className="widget-posters__meta">{t(`media:kind.${card.kind}`)}</span>
          </>
        );
        return (
          <li key={card.id}>{card.route ? <Link to={card.route}>{body}</Link> : <span>{body}</span>}</li>
        );
      })}
    </ul>
  );
}

registerWidgetComponent("media.leaving", Leaving);
