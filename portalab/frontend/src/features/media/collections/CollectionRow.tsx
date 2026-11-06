import { useId } from "react";
import { Link } from "react-router";
import { Icon } from "../../../design-system/components/Icon";
import { useFormat } from "../../../i18n/format/useFormat";
import { useT } from "../../../i18n/hooks/useT";
import { type Collection, collectionPath, imageUrl, type MediaCard, useTitleCollection } from "../api";
import { metadataImage } from "../detail/Enrichment";
import { MediaGrid, Poster } from "../MediaGrid";
import "./collections.css";

/**
 * Issue 361: the collection a title belongs to — a film's saga, a book's or an audiobook's series, a game's
 * franchise — told the same way on every title's page: its name, the title's place in it (« Volume 2 »), its
 * other titles in the library on a rail, and its own page (every title in order; a saga's missing films).
 */
type Item = Collection["items"][number];
export type Word = "saga" | "series" | "franchise";

export const WORD_ICONS: Record<Word, string> = { saga: "film", series: "book", franchise: "joystick" };
const AROUND = 20; // the titles on the rail: a long franchise shows those around this one

/** A saga (films), a franchise (games) or a series (books, audiobooks). */
export function wordOf(collection: Collection): Word {
  if (collection.source === "saga") return "saga";
  return collection.items.length && collection.items.every((item) => item.kind === "game")
    ? "franchise"
    : "series";
}

export function collectionCover(collection: Collection): string | null {
  return (
    metadataImage(collection.poster, "w342") ??
    imageUrl(collection.items.find((item) => item.image_id)?.image_id ?? null)
  );
}

/** What a title's card says of its place: its volume, a game's platform. */
export function useItemNote(): (item: Item) => string | null {
  const t = useT();
  const format = useFormat();
  return (item) =>
    [
      item.position !== null && item.position !== undefined
        ? t("media:collection.volume", { number: format.number(item.position) })
        : null,
      item.platform ?? null,
    ]
      .filter(Boolean)
      .join(" · ") || null;
}

export function CollectionRow({ objectId }: { objectId: string }) {
  const t = useT();
  const headingId = useId();
  const note = useItemNote();
  const found = useTitleCollection(objectId).data;
  if (!found?.name || !Array.isArray(found.items)) return null;
  const word = wordOf(found);
  const index = Math.max(
    0,
    found.items.findIndex((item) => item.id === objectId),
  );
  const start = Math.max(0, Math.min(index - 3, found.items.length - AROUND));
  const shown = found.items.slice(start, start + AROUND);
  const mine = found.items[index];
  const facts = [
    mine && mine.id === objectId ? note(mine) : null,
    t("media:collection.inLibrary", { count: found.items.length }),
  ].filter(Boolean);
  const cover = collectionCover(found);
  return (
    <section aria-labelledby={headingId} className="media-row media-collection">
      <div className="media-collection__head">
        <span className="media-collection__cover">
          <Poster src={cover} kind={found.items[0]?.kind ?? "movie"} />
        </span>
        <div className="media-collection__text">
          <span className="media-collection__word">
            <Icon name={WORD_ICONS[word]} size={14} />
            {t(`media:collection.word.${word}`)}
          </span>
          <h3 id={headingId}>
            <Link to={collectionPath(found.ref)}>{found.name}</Link>
          </h3>
          <p className="media-collection__facts">{facts.join(" · ")}</p>
        </div>
        <Link
          className="ds-button ds-button--secondary media-collection__open"
          to={collectionPath(found.ref)}
        >
          {t(`media:collection.open.${word}`)}
          <Icon name="chevron-right" size={16} />
        </Link>
      </div>
      {found.items.length > 1 ? (
        <MediaGrid
          items={shown as MediaCard[]}
          label={found.name}
          rail
          note={(item) => (item.id === objectId ? t("media:collection.this") : note(item as Item))}
        />
      ) : null}
    </section>
  );
}
