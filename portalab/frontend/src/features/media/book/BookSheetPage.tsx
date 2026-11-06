import { useQuery } from "@tanstack/react-query";
import { useId } from "react";
import { Link, useSearchParams } from "react-router";
import { api } from "../../../api/client";
import { Icon } from "../../../design-system/components/Icon";
import { PageHeader } from "../../../design-system/components/PageHeader";
import { FunctionalState } from "../../../design-system/state/FunctionalState";
import { useFormat } from "../../../i18n/format/useFormat";
import { useT } from "../../../i18n/hooks/useT";
import { useLocaleContext } from "../../../i18n/provider/I18nProvider";
import { ApiError } from "../../../state/regions";
import { useAskOptions } from "../../requests/api";
import { Poster } from "../MediaGrid";
import "../media.css";
import "./book.css";

/**
 * Issue 367: a book the library may lack, as the book database tells it (Hardcover) — its cover, authors, series,
 * genres, rating and description; its editions, the member's language first (a translation's title, its
 * format, publisher and ISBN); where the library has it (as a book, as an audiobook); and, while the
 * requests take its kind, asking the team for it — the book itself or one of its editions. Reached from an
 * absent book on an author's or a series' page.
 */
interface Edition {
  title: string;
  language: string | null;
  format: string | null;
  audio: boolean;
  ids: Record<string, string[]>;
  publisher: string | null;
  year: number | null;
  cover: string | null;
}

interface Sheet {
  service: string;
  ref: string;
  title: string;
  subtitle: string | null;
  description: string | null;
  year: number | null;
  pages: number | null;
  cover: string | null;
  authors: string[];
  series: { name: string; position: number | null; route: string | null }[];
  genres: string[];
  moods: string[];
  rating: number | null;
  votes: number;
  readers: number;
  editions: Edition[];
  library: Record<string, string>;
}

function useBookSheet(service: string, ref: string) {
  return useQuery({
    queryKey: ["media", "book-sheet", service, ref],
    enabled: Boolean(service && ref),
    retry: false,
    staleTime: 10 * 60_000,
    queryFn: async () =>
      (await api.GET("/api/v1/media/book", { params: { query: { service, ref } } })).data as unknown as Sheet,
  });
}

/** Where a request for it begins: its kind, the title (an edition's), its authors, language, edition, ids. */
function askLink(kind: string, title: string, authors: string[], edition?: Edition): string {
  const query = new URLSearchParams({ kind, title });
  if (authors.length) query.set("creator", authors.join(", "));
  if (edition?.year) query.set("year", String(edition.year));
  if (edition?.language) query.set("language", edition.language);
  const said = [edition?.format, edition?.publisher].filter(Boolean).join(", ");
  if (said) query.set("edition", said);
  for (const [scheme, values] of Object.entries(edition?.ids ?? {})) {
    for (const value of values) query.append(`id.${scheme}`, value);
  }
  return `/requests?${query}`;
}

function languageName(code: string | null, locale: string): string | null {
  if (!code) return null;
  try {
    return new Intl.DisplayNames([locale], { type: "language" }).of(code) ?? code;
  } catch {
    return code;
  }
}

export function BookSheetPage() {
  const t = useT();
  const format = useFormat();
  const headingId = useId();
  const { language, locale } = useLocaleContext();
  const [params] = useSearchParams();
  const service = params.get("service") ?? "";
  const ref = params.get("ref") ?? "";
  const sheet = useBookSheet(service, ref);
  const asks = useAskOptions();
  if (sheet.isPending && service && ref) return <FunctionalState state="loading" />;
  if (!sheet.data) {
    const missing = !service || !ref || (sheet.error instanceof ApiError && sheet.error.status === 404);
    return (
      <section aria-labelledby={headingId} className="media-book">
        <PageHeader titleId={headingId} level={2} icon="book" title={t("media:book.title")} />
        {missing ? (
          <p className="ds-panel">{t("media:book.notFound")}</p>
        ) : (
          <FunctionalState state="unavailable" onRetry={() => sheet.refetch()} />
        )}
      </section>
    );
  }
  const book = sheet.data;
  // the member's language first, then the most held
  const editions = [...book.editions].sort(
    (a, b) => Number(b.language === language) - Number(a.language === language),
  );
  const mine = editions.find((e) => e.language === language && !e.audio);
  const canAsk = (kind: string) => Boolean(asks.data?.kinds.includes(kind)) && !book.library[kind];
  const facts = [
    book.year,
    book.pages ? t("media:book.pages", { count: book.pages }) : null,
    book.readers ? t("media:book.readers", { count: book.readers }) : null,
  ].filter(Boolean);
  return (
    <section aria-labelledby={headingId} className="media-book">
      <PageHeader
        titleId={headingId}
        level={2}
        icon="book"
        title={book.title}
        context={book.subtitle ?? undefined}
        primary={
          canAsk("book") ? (
            <Link
              className="ds-button ds-button--primary"
              to={askLink("book", mine?.title ?? book.title, book.authors, mine)}
            >
              <Icon name="plus" size={16} />
              {t("media:ask.askIt")}
            </Link>
          ) : undefined
        }
      />
      <div className="media-person__hero">
        <span className="media-book__cover">
          <Poster src={book.cover} kind="book" />
        </span>
        <div className="media-person__about">
          {book.authors.length ? (
            <p className="media-book__authors">
              {t("media:book.by")}{" "}
              {book.authors.map((name, index) => (
                <span key={name}>
                  {index ? ", " : ""}
                  <Link to={`/media/people/${encodeURIComponent(name)}`}>{name}</Link>
                </span>
              ))}
            </p>
          ) : null}
          {facts.length ? <p className="media-book__facts">{facts.join(" · ")}</p> : null}
          {book.rating !== null ? (
            <p className="media-book__facts">
              <Icon name="star" size={14} /> {format.number(book.rating)}/10 ·{" "}
              {t("media:book.votes", { count: book.votes })}
            </p>
          ) : null}
          {Object.keys(book.library).length ? (
            <ul className="media-book__library">
              {Object.entries(book.library).map(([kind, id]) => (
                <li key={kind}>
                  <Link className="ds-button ds-button--secondary" to={`/media/${id}`}>
                    <Icon name="check" size={14} />
                    {t("media:book.inLibrary", { kind: t(`media:kind.${kind}`) })}
                  </Link>
                </li>
              ))}
            </ul>
          ) : (
            <p className="media-person__absent">{t("media:book.absent")}</p>
          )}
          {book.series.length ? (
            <ul className="media-book__series" aria-label={t("media:book.series")}>
              {book.series.map((s) => {
                const label =
                  s.position !== null
                    ? t("media:book.volume", { name: s.name, number: format.number(s.position) })
                    : s.name;
                return <li key={s.name}>{s.route ? <Link to={s.route}>{label}</Link> : label}</li>;
              })}
            </ul>
          ) : null}
          {book.genres.length || book.moods.length ? (
            <ul className="media-person__roles" aria-label={t("media:book.genres")}>
              {[...book.genres, ...book.moods].map((tag) => (
                <li key={tag}>{tag}</li>
              ))}
            </ul>
          ) : null}
        </div>
      </div>
      {book.description ? (
        <section className="media-book__about">
          <h3>{t("media:book.about")}</h3>
          {book.description.split(/\n+/).map((part, index) => (
            // biome-ignore lint/suspicious/noArrayIndexKey: paragraphs of one text, never reordered
            <p key={index}>{part}</p>
          ))}
        </section>
      ) : null}
      {editions.length ? (
        <section className="media-book__editions">
          <h3>{t("media:book.editions")}</h3>
          <ul aria-label={t("media:book.editions")}>
            {editions.map((edition, index) => {
              const kind = edition.audio ? "audiobook" : "book";
              return (
                // biome-ignore lint/suspicious/noArrayIndexKey: editions may share every field shown
                <li key={index} className="media-book__edition">
                  <span className="media-book__edition-cover">
                    <Poster src={edition.cover} kind={kind} />
                  </span>
                  <span className="media-book__edition-text">
                    <strong>{edition.title}</strong>
                    <span className="media-book__facts">
                      {[
                        languageName(edition.language, locale),
                        edition.audio ? t("media:kind.audiobook") : edition.format,
                        edition.publisher,
                        edition.year,
                      ]
                        .filter(Boolean)
                        .join(" · ")}
                    </span>
                    {edition.ids.isbn?.[0] ? (
                      <span className="media-book__facts">
                        {t("media:book.isbn", { isbn: edition.ids.isbn[0] })}
                      </span>
                    ) : null}
                  </span>
                  {canAsk(kind) ? (
                    <Link
                      className="media-person__ask"
                      to={askLink(kind, edition.title, book.authors, edition)}
                    >
                      <Icon name="plus" size={14} />
                      {t("media:ask.askIt")}
                    </Link>
                  ) : null}
                </li>
              );
            })}
          </ul>
        </section>
      ) : null}
      <p className="media-book__source">{t("media:book.source")}</p>
    </section>
  );
}

export default BookSheetPage;
