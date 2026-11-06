import { useId } from "react";
import { Link, useSearchParams } from "react-router";
import { PageHeader } from "../../../design-system/components/PageHeader";
import { FunctionalState } from "../../../design-system/state/FunctionalState";
import { useT } from "../../../i18n/hooks/useT";
import { type Collection, MediaError, useCollection } from "../api";
import { MediaGrid, Poster } from "../MediaGrid";
import { KnownCard } from "../people/PersonPage";
import { collectionCover, useItemNote, WORD_ICONS, wordOf } from "./CollectionRow";
import "../media.css";
import "./collections.css";

/**
 * Issue 361: a collection's page — a book's series in its volumes' order, a game's franchise, a film's saga
 * with every film TMDB knows of it (those the library has, those asked for, those to ask for); issue 362: a
 * book series with every volume a book database knows (Hardcover), those the library has and the others.
 * Reached from the collection's block on each of its titles' pages.
 */
export function CollectionPage() {
  const t = useT();
  const headingId = useId();
  const [params] = useSearchParams();
  const ref = params.get("ref") ?? "";
  const found = useCollection(ref);
  if (found.isPending && ref) return <FunctionalState state="loading" />;
  if (!found.data) {
    const missing = !ref || (found.error instanceof MediaError && found.error.status === 404);
    return (
      <section aria-labelledby={headingId} className="media-collection-page">
        <PageHeader titleId={headingId} level={2} icon="layers" title={t("media:collection.title")} />
        {missing ? (
          <p className="ds-panel">{t("media:collection.notFound")}</p>
        ) : (
          <FunctionalState state="unavailable" onRetry={() => found.refetch()} />
        )}
        <Link className="ds-button ds-button--secondary" to="/media">
          {t("media:collection.back")}
        </Link>
      </section>
    );
  }
  return <CollectionView headingId={headingId} data={found.data} />;
}

function CollectionView({ headingId, data }: { headingId: string; data: Collection }) {
  const t = useT();
  const note = useItemNote();
  const word = wordOf(data);
  const parts = data.parts ?? [];
  const partsHeading = t(data.source === "saga" ? "media:collection.films" : "media:collection.volumes");
  const told = new Set(parts.map((part) => part.object_id).filter(Boolean));
  // a film of the library the provider does not list in the saga (yet): still one of its titles
  const others = data.items.filter((item) => !told.has(item.id));
  const available = parts.length
    ? parts.filter((part) => part.status === "available").length
    : data.items.filter((item) => item.available).length;
  const stats = [
    { key: "library", value: data.items.length, tone: "accent" },
    { key: "available", value: available, tone: "ok" },
    {
      key: "missing",
      value: parts.filter((part) => part.status === "missing" || part.status === "unavailable").length,
      tone: "neutral",
    },
    // issue 362: a series' volumes not in the library (no service asks for books)
    { key: "absent", value: parts.filter((part) => part.status === "absent").length, tone: "neutral" },
  ].filter((stat) => stat.key === "library" || stat.value > 0);
  return (
    <section aria-labelledby={headingId} className="media-collection-page">
      <PageHeader titleId={headingId} level={2} icon={WORD_ICONS[word]} title={data.name} />
      <div className="media-person__hero">
        <span className="media-collection__cover media-collection__cover--large">
          <Poster src={collectionCover(data)} kind={data.items[0]?.kind ?? "movie"} />
        </span>
        <div className="media-person__about">
          <ul className="media-person__roles">
            <li>{t(`media:collection.word.${word}`)}</li>
          </ul>
          <ul className="media-person__stats">
            {stats.map((stat) => (
              <li key={stat.key} data-tone={stat.tone}>
                <strong>{stat.value}</strong>
                <span>{t(`media:collection.stat.${stat.key}`, { count: stat.value })}</span>
              </li>
            ))}
          </ul>
        </div>
      </div>
      {parts.length ? (
        <section className="media-row">
          <h3>{partsHeading}</h3>
          <ul className="media-grid" aria-label={partsHeading}>
            {parts.map((credit) => (
              <KnownCard key={credit.tmdb_id} credit={credit} askable={data.askable ?? false} />
            ))}
          </ul>
        </section>
      ) : null}
      {others.length ? (
        <section className="media-row">
          {parts.length ? <h3>{t("media:collection.alsoInLibrary")}</h3> : null}
          <MediaGrid
            items={others}
            label={data.name}
            note={(item) => note(item as (typeof others)[number])}
          />
        </section>
      ) : null}
    </section>
  );
}

export default CollectionPage;
