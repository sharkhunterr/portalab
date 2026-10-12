import { useId } from "react";
import { Link } from "react-router";
import { Icon } from "../../../design-system/components/Icon";
import { Skeleton } from "../../../design-system/components/Placeholders";
import { useT } from "../../../i18n/hooks/useT";
import { metadataImage } from "../detail/Enrichment";
import { Poster } from "../MediaGrid";
import { type DiscoverShelf, type Requestable, useDiscoverShelf } from "./api";
import { StatusBadge } from "./StatusBadge";
import "./discover.css";

/** A title one can ask for, as a poster card: its state on the poster, a click to its page. */
export function RequestableCard({ item }: { item: Requestable }) {
  const t = useT();
  return (
    <li className="media-card discover-card" data-status={item.status}>
      <Link to={item.route} className="media-card__link">
        <span className="media-card__frame">
          <Poster src={metadataImage(item.poster, "w342")} kind={item.kind} />
          <span className="discover-card__badge">
            <StatusBadge item={item} />
          </span>
        </span>
        <span className="media-card__title">{item.title}</span>
      </Link>
      <span className="media-card__meta">
        {t(`media:kind.${item.kind}`)}
        {item.year ? ` · ${item.year}` : ""}
      </span>
    </li>
  );
}

const SHELVES: Array<{ name: DiscoverShelf; icon: string }> = [
  { name: "trending", icon: "trending" },
  { name: "popular_movies", icon: "film" },
  { name: "popular_series", icon: "tv" },
  { name: "upcoming_movies", icon: "calendar" },
  { name: "upcoming_series", icon: "calendar" },
];

function Shelf({ name, icon }: { name: DiscoverShelf; icon: string }) {
  const t = useT();
  const headingId = useId();
  const shelf = useDiscoverShelf(name);
  if (shelf.isError || (shelf.data && (!shelf.data.configured || !shelf.data.items.length))) return null;
  return (
    <section aria-labelledby={headingId} className="media-row discover-row">
      <header className="media-row__head">
        <h3 id={headingId}>
          <Icon name={icon} size={18} />
          {t(`media:discover.shelf.${name}`)}
        </h3>
      </header>
      {shelf.isPending ? (
        <Skeleton shape="tile" count={5} label={t(`media:discover.shelf.${name}`)} />
      ) : (
        <ul className="media-rail" aria-label={t(`media:discover.shelf.${name}`)}>
          {shelf.data.items.map((item) => (
            <RequestableCard key={`${item.kind}-${item.tmdb_id}`} item={item} />
          ))}
        </ul>
      )}
    </section>
  );
}

/**
 * #4: the request service's shelves in Media, like Seerr's home — trending, popular and upcoming films and
 * series — each title with its state (available, asked for by me or by a member) and a click to ask for
 * it. Nothing when no request service is connected.
 */
export function DiscoverShelves() {
  return (
    <>
      {SHELVES.map((shelf) => (
        <Shelf key={shelf.name} name={shelf.name} icon={shelf.icon} />
      ))}
    </>
  );
}
