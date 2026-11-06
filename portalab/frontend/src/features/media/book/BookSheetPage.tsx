import { useQuery } from "@tanstack/react-query";
import { useId } from "react";
import { Link, Navigate, useSearchParams } from "react-router";
import { api } from "../../../api/client";
import { Icon } from "../../../design-system/components/Icon";
import { PageHeader } from "../../../design-system/components/PageHeader";
import { FunctionalState } from "../../../design-system/state/FunctionalState";
import { useFormat } from "../../../i18n/format/useFormat";
import { useT } from "../../../i18n/hooks/useT";
import { useLocaleContext } from "../../../i18n/provider/I18nProvider";
import { ApiError } from "../../../state/regions";
import { AskDialog } from "../../requests/AskDialog";
import { useAskOptions } from "../../requests/api";
import type { AskStart } from "../../requests/RequestsPage";
import { BookFacts } from "../detail/BookView";
import { TitleHero } from "../detail/TitleHero";
import { Poster } from "../MediaGrid";
import "../media.css";
import "./book.css";

/**
 * Issue 367: a book the library may lack, as the book database tells it (Hardcover); issue 370: laid out as a
 * library title's page (the same head, facts, summary, genres, authors) — its cover, authors, series,
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
  release_date: string | null;
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
function askStart(kind: string, title: string, authors: string[], edition?: Edition): AskStart {
  return {
    kind,
    cover: edition?.cover ?? null,
    sheet: `${window.location.pathname}${window.location.search}`, // issue 378: back to this sheet
    title,
    creator: authors.join(", ") || undefined,
    year: edition?.year ?? null,
    language: edition?.language ?? null,
    edition: [edition?.format, edition?.publisher].filter(Boolean).join(", ") || null,
    ids: edition?.ids ?? {},
  };
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
  // one page per title: the library's (same look, with reading) when it has the book itself; an audiobook
  // only (issue 374) leaves the book to ask for, its audiobook one click away
  if (book.library.book) return <Navigate to={`/media/${book.library.book}`} replace />;
  const listened = book.library.audiobook;
  // the editions in the member's language first (the service keeps those in its languages)
  const editions = [...book.editions].sort(
    (a, b) => Number(b.language === language) - Number(a.language === language),
  );
  const mine = editions.find((e) => e.language === language && !e.audio);
  const title = mine?.title ?? book.title;
  const canAsk = (kind: string) => Boolean(asks.data?.kinds.includes(kind)) && !book.library[kind];
  return (
    <article aria-labelledby={headingId} className="media-detail media-book">
      {/* issue 370: the same head and book page as a title of the library */}
      <TitleHero
        headingId={headingId}
        level={2}
        title={title}
        kind="book"
        poster={mine?.cover ?? book.cover}
        backdrop={null}
        facts={[
          book.year ? String(book.year) : null,
          t("media:kind.book"),
          book.pages ? t("media:facts.pageCount", { count: book.pages }) : null,
          book.rating !== null ? `★ ${format.number(book.rating)}` : null,
        ]}
        badges={
          listened ? (
            <Link className="ds-button ds-button--secondary" to={`/media/${listened}`}>
              <Icon name="headphones" size={14} />
              {t("media:book.listened")}
            </Link>
          ) : (
            <span className="media-person__absent">{t("media:book.absent")}</span>
          )
        }
        primary={
          canAsk("book") ? (
            <AskDialog
              start={{ ...askStart("book", title, book.authors, mine), cover: mine?.cover ?? book.cover }}
              trigger={
                <button type="button" className="ds-button ds-button--primary">
                  <Icon name="plus" size={16} />
                  {t("media:ask.askIt")}
                </button>
              }
            />
          ) : null
        }
      />
      <BookFacts
        data={{
          title,
          original_title: book.title,
          overview: book.description,
          released: book.release_date,
          rating: book.rating,
          pages: book.pages,
          authors: book.authors,
          tags: book.moods,
        }}
        genres={book.genres}
      />
      {book.series.length ? (
        <section className="media-enriched" aria-label={t("media:book.series")}>
          <div className="media-enriched__block">
            <h3>{t("media:book.series")}</h3>
            <ul className="media-book__series">
              {book.series.map((s) => {
                const label =
                  s.position !== null
                    ? t("media:book.volume", { name: s.name, number: format.number(s.position) })
                    : s.name;
                return <li key={s.name}>{s.route ? <Link to={s.route}>{label}</Link> : label}</li>;
              })}
            </ul>
          </div>
        </section>
      ) : null}
      {editions.length ? (
        <section className="media-enriched" aria-label={t("media:book.editions")}>
          <div className="media-enriched__block">
            <h3>{t("media:book.editions")}</h3>
            <ul className="media-book__editions" aria-label={t("media:book.editions")}>
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
                      <AskDialog
                        start={askStart(kind, edition.title, book.authors, edition)}
                        trigger={
                          <button type="button" className="media-person__ask">
                            <Icon name="plus" size={14} />
                            {t("media:ask.askIt")}
                          </button>
                        }
                      />
                    ) : null}
                  </li>
                );
              })}
            </ul>
          </div>
        </section>
      ) : null}
      <p className="media-book__source">
        {t("media:book.source")}
        {book.readers ? ` ${t("media:book.readers", { count: book.readers })}.` : ""}
      </p>
    </article>
  );
}

export default BookSheetPage;
