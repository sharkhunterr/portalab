import { Link } from "react-router";
import { Icon } from "../../../design-system/components/Icon";
import { useFormat } from "../../../i18n/format/useFormat";
import { useT } from "../../../i18n/hooks/useT";
import { personPath, usePerson, useSection } from "../api";
import { useMeasures } from "../insights/api";

type Data = Record<string, unknown>;

function names(value: unknown): string[] {
  return Array.isArray(value) ? (value as string[]).filter((name) => typeof name === "string") : [];
}

/** #92: a book's or an audiobook's authors and narrators, read once — the same split everywhere. */
export function bookPeople(data: Data): { authors: string[]; narrators: string[] } {
  const narrators = names(data.narrators);
  const authors = names(data.authors).length
    ? names(data.authors)
    : names(data.people).filter((name) => !narrators.includes(name));
  return { authors, narrators };
}

/** A person of the book, as on a film's cast: their portrait (from whichever service has one), name, role. */
function Person({ name, role }: { name: string; role: string }) {
  const person = usePerson(name);
  const src = person.data?.portrait ?? null;
  return (
    <li>
      <Link className="media-enriched__person" to={personPath(name)}>
        <span className="media-enriched__portrait">
          {src ? <img src={src} alt="" loading="lazy" /> : <Icon name="user" size={28} />}
        </span>
        <strong>{name}</strong>
      </Link>
      <span className="media-muted">{role}</span>
    </li>
  );
}

/**
 * #92 — a book's or an audiobook's page laid out like a film's: its facts as chips (published, length,
 * readers' rating, pages, language), its summary, genres, its authors and narrators with their portraits,
 * then its series and edition as blocks, and its tags — from what the library's services know (Grimmory…).
 */
export function BookView({ objectId, genres }: { objectId: string; genres: string[] }) {
  const info = useSection(objectId, "info");
  if (!info.data) return null;
  return <BookFacts data={(info.data.data ?? {}) as Data} genres={genres} />;
}

/** The same book page from any source — the library's services, or a book database for a book the
 * library lacks (issue 370). */
export function BookFacts({ data, genres }: { data: Data; genres: string[] }) {
  const t = useT();
  const format = useFormat();
  const measures = useMeasures();
  const { authors, narrators } = bookPeople(data);
  const facts = [
    data.released
      ? {
          key: "released",
          icon: "calendar",
          value: format.date(`${String(data.released)}T12:00:00Z`, "long"),
        }
      : null,
    data.duration_s
      ? { key: "length", icon: "clock", value: measures.duration(Number(data.duration_s)) }
      : null,
    data.rating
      ? {
          key: "rating",
          icon: "star",
          value: `${format.number(Math.round(Number(data.rating) * 10) / 10)}/10`,
        }
      : null,
    data.pages
      ? { key: "pages", icon: "book", value: t("media:facts.pageCount", { count: Number(data.pages) }) }
      : null,
    data.language ? { key: "language", icon: "globe", value: String(data.language).toUpperCase() } : null,
  ].filter((fact) => fact !== null);
  const edition = [
    data.publisher ? { key: "publisher", value: String(data.publisher) } : null,
    data.released
      ? { key: "released", value: format.date(`${String(data.released)}T12:00:00Z`, "long") }
      : null,
    data.isbn ? { key: "isbn", value: String(data.isbn) } : null,
    data.asin ? { key: "asin", value: String(data.asin) } : null,
  ].filter((row) => row !== null);
  const tags = names(data.tags);
  const people = [
    ...authors.map((name) => ({ name, role: t("media:facts.author") })),
    ...narrators.map((name) => ({ name, role: t("media:facts.narrator") })),
  ];
  return (
    <section className="media-enriched" aria-label={t("media:detail.section.info")}>
      {data.original_title && data.original_title !== data.title ? (
        <p className="media-enriched__tagline">{String(data.original_title)}</p>
      ) : null}
      {facts.length ? (
        <ul className="media-enriched__facts">
          {facts.map((fact) => (
            <li key={fact.key}>
              <Icon name={fact.icon} size={16} />
              {fact.value}
            </li>
          ))}
        </ul>
      ) : null}
      {data.overview ? <p className="media-enriched__overview">{String(data.overview)}</p> : null}
      {genres.length ? (
        <ul className="media-enriched__chips" aria-label={t("media:enriched.genres")}>
          {genres.map((genre) => (
            <li key={genre}>{genre}</li>
          ))}
        </ul>
      ) : null}
      {people.length ? (
        <div className="media-enriched__block">
          <h3>{t("media:facts.people")}</h3>
          <ul className="media-enriched__cast">
            {people.map((person) => (
              <Person key={`${person.name}-${person.role}`} name={person.name} role={person.role} />
            ))}
          </ul>
        </div>
      ) : null}
      {/* issue 361: its series is told by the collection's block, with its other volumes */}
      {edition.length ? (
        <div className="media-enriched__grid">
          <div className="media-enriched__block">
            <h3>{t("media:facts.edition")}</h3>
            <dl className="media-enriched__pairs">
              {edition.map((row) => (
                <div key={row.key}>
                  <dt>{t(`media:facts.${row.key}`)}</dt>
                  <dd>{row.value}</dd>
                </div>
              ))}
            </dl>
          </div>
        </div>
      ) : null}
      {tags.length ? (
        <ul className="media-enriched__chips media-enriched__chips--quiet" aria-label={t("media:facts.tags")}>
          {tags.map((tag) => (
            <li key={tag}>#{tag}</li>
          ))}
        </ul>
      ) : null}
    </section>
  );
}
