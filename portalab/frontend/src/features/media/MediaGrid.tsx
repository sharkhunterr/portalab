import { type ReactNode, useState } from "react";
import { Link } from "react-router";
import { usePreferences } from "../../design-system/a11y/PreferencesProvider";
import { Icon } from "../../design-system/components/Icon";
import { useT } from "../../i18n/hooks/useT";
import { PosterTickets } from "../support/tickets/MediaTickets";
import { AgeBadge } from "./AgeBadge";
import { useAge } from "./ages";
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
/** A title's poster — issue 434: with its age rating's badge when the title is known (``mediaId``; its
 * ``age`` when the card carries it) and the member keeps the badges on thumbnails. */
export function Poster({
  src,
  kind,
  mediaId,
  age,
}: {
  src: string | null;
  kind: string;
  mediaId?: string | null | undefined;
  age?: number | null | undefined;
}) {
  const [broken, setBroken] = useState(false);
  const shown = usePreferences().preferences.cardAgeBadge;
  const asked = useAge(mediaId, shown && age === undefined);
  const rating = age !== undefined ? age : asked.data;
  return (
    <>
      {src && !broken ? (
        <img src={src} alt="" loading="lazy" className="media-card__poster" onError={() => setBroken(true)} />
      ) : (
        <span className="media-card__poster media-card__poster--none" aria-hidden="true">
          <Icon name={KIND_ICONS[kind] ?? "film"} size={34} />
        </span>
      )}
      {shown && mediaId ? <AgeBadge age={rating} compact /> : null}
    </>
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
        <li
          key={item.id}
          className="media-card"
          data-available={item.available}
          data-locked={("locked" in item && item.locked) || undefined}
        >
          <Link to={`/media/${item.id}`} className="media-card__link">
            <span className="media-card__frame">
              <Poster
                src={imageUrl(item.image_id)}
                kind={item.kind}
                mediaId={item.id}
                age={"age" in item ? (item.age ?? null) : undefined}
              />
              {"locked" in item && item.locked ? (
                // 032: above this household profile's age rating, shown locked by its master's choice
                <span className="media-card__lock" title={t("household:lockedBadge")}>
                  <Icon name="lock" size={22} />
                  <span className="visually-hidden">{t("household:lockedBadge")}</span>
                </span>
              ) : "kept" in item && item.kept ? (
                // issue 432: shown to this profile, its page opens, never played — a small padlock
                <span className="media-card__kept" title={t("household:kept.badge")}>
                  <Icon name="lock" size={14} />
                  <span className="visually-hidden">{t("household:kept.badge")}</span>
                </span>
              ) : null}
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
