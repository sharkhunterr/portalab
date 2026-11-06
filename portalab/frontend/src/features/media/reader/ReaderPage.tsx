import { type CSSProperties, useCallback, useEffect, useMemo, useState } from "react";
import { useParams } from "react-router";
import { Icon } from "../../../design-system/components/Icon";
import { useFormat } from "../../../i18n/format/useFormat";
import { useT } from "../../../i18n/hooks/useT";
import { ApiError } from "../../../state/regions";
import { type BookFormat, useReadInfo } from "../books/api";
import { ComicView } from "./ComicView";
import { EpubView } from "./EpubView";
import { PdfView } from "./PdfView";
import { useBookmarks, useReaderSettings, useReadingSession } from "./session";
import type { Controls, Heading, Hit } from "./types";
import "../player/player.css";
import "./reader.css";

const OPENS = ["epub", "pdf", "cbx"];
const PREFERRED = ["epub", "pdf", "cbx"];

/** Leaving the reader reloads the title's page: the portal's stricter policy comes back with it. */
function leave(objectId: string) {
  window.location.assign(`/media/${objectId}`);
}

/**
 * ``/media/:objectId/read`` (#21): the book over the whole window — EPUB, PDF or comic book archive, its table
 * of contents, search, bookmarks, the member's reading settings, full screen; where they stop goes back to
 * the portal and the library.
 */
export function ReaderPage() {
  const t = useT();
  const { objectId = "" } = useParams();
  const info = useReadInfo(objectId);
  const [chosen, setChosen] = useState<string | null>(null);

  useEffect(() => {
    document.documentElement.dataset.playing = "true"; // the shell steps aside
    return () => {
      delete document.documentElement.dataset.playing;
    };
  }, []);

  const formats = useMemo(
    () => (info.data?.book.formats ?? []).filter((f) => OPENS.includes(f.format)),
    [info.data],
  );
  const format = useMemo(() => {
    if (!formats.length) return null;
    const byRef = formats.find((f) => f.file_ref === chosen);
    if (byRef) return byRef;
    const last = [...(info.data?.resume ?? [])].sort((a, b) => b.percent - a.percent)[0];
    return (
      formats.find((f) => f.format === last?.format) ??
      PREFERRED.map((name) => formats.find((f) => f.format === name)).find(Boolean) ??
      null
    );
  }, [formats, chosen, info.data]);

  if (info.isPending) {
    return (
      <div className="reader-page" data-state="loading">
        <div className="player-spinner" role="status" aria-label={t("media:reader.loading")} />
      </div>
    );
  }
  if (info.isError || !info.data || !format) {
    const code = info.error instanceof ApiError ? info.error.code : undefined;
    const reason = !info.isError
      ? "format"
      : code === "media.books_disabled"
        ? "disabled"
        : code === "media.books_nothing"
          ? "nothing"
          : "unavailable";
    return (
      <div className="reader-page" data-state="error">
        <div className="player-failure reader-failure" role="alert">
          <Icon name="book-open" size={28} />
          <p>{t(`media:reader.error.${reason}`)}</p>
          <div>
            {reason === "unavailable" ? (
              <button type="button" className="player-pill" data-primary onClick={() => info.refetch()}>
                {t("media:reader.retry")}
              </button>
            ) : null}
            <button type="button" className="player-pill" onClick={() => leave(objectId)}>
              {t("media:reader.back")}
            </button>
          </div>
        </div>
      </div>
    );
  }
  return (
    <Reader
      key={format.file_ref}
      objectId={objectId}
      info={info.data}
      format={format}
      formats={formats}
      onFormat={setChosen}
    />
  );
}

function Reader({
  objectId,
  info,
  format,
  formats,
  onFormat,
}: {
  objectId: string;
  info: NonNullable<ReturnType<typeof useReadInfo>["data"]>;
  format: BookFormat;
  formats: BookFormat[];
  onFormat(ref: string): void;
}) {
  const t = useT();
  const number = useFormat();
  const [settings, update] = useReaderSettings();
  const session = useReadingSession(info.ticket, format.format, format.file_ref);
  const bookmarks = useBookmarks(objectId, format.format);
  const resume = info.resume.find((r) => r.format === format.format);
  const [toc, setToc] = useState<Heading[]>([]);
  const [controls, setControls] = useState<Controls | null>(null);
  const [panel, setPanel] = useState<"toc" | "search" | "bookmarks" | "settings" | null>(null);
  const [failed, setFailed] = useState(false);
  const [zoom, setZoom] = useState(1);
  const [query, setQuery] = useState("");
  const [hits, setHits] = useState<Hit[] | null>(null);
  const [searching, setSearching] = useState(false);
  const [chrome, setChrome] = useState(true);

  const ready = useCallback((headings: Heading[], given: Controls) => {
    setToc(headings);
    setControls(given);
  }, []);
  const failedOnce = useCallback(() => setFailed(true), []);
  const close = () => {
    session.stop();
    leave(objectId);
  };
  const fullscreen = () => {
    if (document.fullscreenElement) void document.exitFullscreen();
    else void document.documentElement.requestFullscreen?.().catch(() => undefined);
  };
  const share = session.current?.percent ?? resume?.percent ?? 0;
  const left = session.minutesLeft();
  const view = {
    ticket: info.ticket,
    objectId,
    format,
    resume,
    settings,
    onMoved: session.moved,
    onReady: ready,
    onFailed: failedOnce,
  };
  const pick = (target: string) => {
    controls?.goto(target);
    setPanel(null);
  };

  return (
    <div className="reader-page" data-chrome={chrome || undefined}>
      <header className="reader-bar">
        <button
          type="button"
          className="player-icon reader-icon"
          onClick={close}
          aria-label={t("media:reader.back")}
        >
          <Icon name="chevron-left" size={22} />
        </button>
        <div className="reader-bar__title">
          <strong>{info.book.title}</strong>
          {info.book.author ? <small>{info.book.author}</small> : null}
        </div>
        {formats.length > 1 ? (
          <select
            className="reader-format"
            value={format.file_ref}
            onChange={(e) => onFormat(e.target.value)}
            aria-label={t("media:reader.format")}
          >
            {formats.map((f) => (
              <option key={f.file_ref} value={f.file_ref}>
                {f.format.toUpperCase()}
              </option>
            ))}
          </select>
        ) : null}
        <button
          type="button"
          className="player-icon reader-icon"
          aria-label={t("media:reader.contents")}
          aria-pressed={panel === "toc"}
          onClick={() => setPanel(panel === "toc" ? null : "toc")}
          disabled={!toc.length}
        >
          <Icon name="list" size={20} />
        </button>
        {controls?.search ? (
          <button
            type="button"
            className="player-icon reader-icon"
            aria-label={t("media:reader.search")}
            aria-pressed={panel === "search"}
            onClick={() => setPanel(panel === "search" ? null : "search")}
          >
            <Icon name="search" size={20} />
          </button>
        ) : null}
        <button
          type="button"
          className="player-icon reader-icon"
          aria-label={t("media:reader.bookmarks")}
          aria-pressed={panel === "bookmarks"}
          onClick={() => setPanel(panel === "bookmarks" ? null : "bookmarks")}
        >
          <Icon name="bookmark" size={20} />
        </button>
        <button
          type="button"
          className="player-icon reader-icon"
          aria-label={t("media:reader.settings")}
          aria-pressed={panel === "settings"}
          onClick={() => setPanel(panel === "settings" ? null : "settings")}
        >
          <Icon name="type" size={20} />
        </button>
        <button
          type="button"
          className="player-icon reader-icon"
          onClick={fullscreen}
          aria-label={t("media:reader.fullscreen")}
        >
          <Icon name="maximize" size={20} />
        </button>
      </header>

      <main className="reader-main" onDoubleClick={() => setChrome((c) => !c)}>
        {failed ? (
          <div className="player-failure reader-failure" role="alert">
            <p>{t("media:reader.error.file")}</p>
            <button type="button" className="player-pill" onClick={close}>
              {t("media:reader.back")}
            </button>
          </div>
        ) : format.format === "epub" ? (
          <EpubView {...view} />
        ) : format.format === "pdf" ? (
          <PdfView {...view} zoom={zoom} />
        ) : (
          <ComicView {...view} />
        )}
      </main>

      {panel ? (
        <aside
          className="reader-panel"
          aria-label={t(`media:reader.${panel === "toc" ? "contents" : panel}`)}
        >
          <div className="reader-panel__head">
            <h2>{t(`media:reader.${panel === "toc" ? "contents" : panel}`)}</h2>
            <button
              type="button"
              className="player-icon reader-icon"
              onClick={() => setPanel(null)}
              aria-label={t("media:reader.closePanel")}
            >
              <Icon name="close" size={18} />
            </button>
          </div>
          {panel === "toc" ? (
            <ol className="reader-list">
              {toc.map((heading) => (
                <li
                  key={`${heading.target}-${heading.label}`}
                  style={{ paddingInlineStart: `${heading.depth}rem` }}
                >
                  <button type="button" onClick={() => pick(heading.target)}>
                    {heading.label}
                  </button>
                </li>
              ))}
            </ol>
          ) : null}
          {panel === "search" ? (
            <div className="reader-search">
              <form
                onSubmit={(event) => {
                  event.preventDefault();
                  if (!controls?.search || query.trim().length < 2) return;
                  setSearching(true);
                  void controls
                    .search(query.trim())
                    .then(setHits)
                    .finally(() => setSearching(false));
                }}
              >
                <input
                  type="search"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder={t("media:reader.searchPlaceholder")}
                  aria-label={t("media:reader.search")}
                />
                <button type="submit" className="ds-button ds-button--secondary" disabled={searching}>
                  {t("media:reader.find")}
                </button>
              </form>
              {searching ? <p role="status">{t("media:reader.searching")}</p> : null}
              {hits ? (
                hits.length ? (
                  <ol className="reader-list">
                    {hits.map((hit, i) => (
                      // biome-ignore lint/suspicious/noArrayIndexKey: one search's results, in order
                      <li key={i}>
                        <button type="button" onClick={() => pick(hit.target)}>
                          {hit.excerpt}
                        </button>
                      </li>
                    ))}
                  </ol>
                ) : (
                  <p>{t("media:reader.noHits")}</p>
                )
              ) : null}
            </div>
          ) : null}
          {panel === "bookmarks" ? (
            <div className="reader-bookmarks">
              <button
                type="button"
                className="ds-button ds-button--secondary"
                disabled={!session.current}
                onClick={() =>
                  session.current &&
                  bookmarks.add({
                    position: session.current.position,
                    percent: session.current.percent,
                    label: t("media:reader.bookmarkAt", { percent: number.percent(session.current.percent) }),
                  })
                }
              >
                <Icon name="bookmark" size={16} />
                {t("media:reader.addBookmark")}
              </button>
              {bookmarks.marks.length ? (
                <ol className="reader-list">
                  {bookmarks.marks.map((mark) => (
                    <li key={mark.position} className="reader-list__mark">
                      <button type="button" onClick={() => pick(mark.position)}>
                        {mark.label}
                      </button>
                      <button
                        type="button"
                        className="player-icon reader-icon"
                        onClick={() => bookmarks.remove(mark.position)}
                        aria-label={t("media:reader.removeBookmark")}
                      >
                        <Icon name="close" size={14} />
                      </button>
                    </li>
                  ))}
                </ol>
              ) : (
                <p>{t("media:reader.noBookmarks")}</p>
              )}
            </div>
          ) : null}
          {panel === "settings" ? (
            <div className="reader-settings">
              <fieldset>
                <legend>{t("media:reader.theme")}</legend>
                {(["auto", "light", "sepia", "dark"] as const).map((theme) => (
                  <label key={theme} data-swatch={theme}>
                    <input
                      type="radio"
                      name="reader-theme"
                      checked={settings.theme === theme}
                      onChange={() => update({ theme })}
                    />
                    {t(`media:reader.themes.${theme}`)}
                  </label>
                ))}
              </fieldset>
              {format.format === "epub" ? (
                <>
                  <label>
                    {t("media:reader.font")}
                    <select
                      value={settings.font}
                      onChange={(e) => update({ font: e.target.value as typeof settings.font })}
                    >
                      {(["publisher", "serif", "sans", "dyslexic"] as const).map((font) => (
                        <option key={font} value={font}>
                          {t(`media:reader.fonts.${font}`)}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label>
                    {t("media:reader.size", { percent: settings.size })}
                    <input
                      type="range"
                      min={70}
                      max={200}
                      step={10}
                      value={settings.size}
                      onChange={(e) => update({ size: Number(e.target.value) })}
                    />
                  </label>
                  <label>
                    {t("media:reader.lineHeight")}
                    <input
                      type="range"
                      min={1.1}
                      max={2.2}
                      step={0.1}
                      value={settings.lineHeight}
                      onChange={(e) => update({ lineHeight: Number(e.target.value) })}
                    />
                  </label>
                  <label>
                    {t("media:reader.margins")}
                    <input
                      type="range"
                      min={0}
                      max={6}
                      step={0.5}
                      value={settings.margin}
                      onChange={(e) => update({ margin: Number(e.target.value) })}
                    />
                  </label>
                  <label className="reader-settings__check">
                    <input
                      type="checkbox"
                      checked={settings.flow === "scrolled"}
                      onChange={(e) => update({ flow: e.target.checked ? "scrolled" : "paginated" })}
                    />
                    {t("media:reader.scrolled")}
                  </label>
                </>
              ) : null}
              {format.format === "pdf" || format.format === "cbx" ? (
                // issue 359: the whole page on the screen, or as wide as the screen (scrolled down)
                <fieldset>
                  <legend>{t("media:reader.fit")}</legend>
                  {(["page", "width"] as const).map((fit) => (
                    <label key={fit}>
                      <input
                        type="radio"
                        name="reader-fit"
                        checked={settings.fit === fit}
                        onChange={() => update({ fit })}
                      />
                      {t(`media:reader.fits.${fit}`)}
                    </label>
                  ))}
                </fieldset>
              ) : null}
              {format.format === "pdf" ? (
                <div className="reader-settings__zoom">
                  <button
                    type="button"
                    className="player-icon reader-icon"
                    onClick={() => setZoom((z) => Math.max(0.5, z - 0.25))}
                    aria-label={t("media:reader.zoomOut")}
                  >
                    −
                  </button>
                  <span>{number.percent(zoom)}</span>
                  <button
                    type="button"
                    className="player-icon reader-icon"
                    onClick={() => setZoom((z) => Math.min(4, z + 0.25))}
                    aria-label={t("media:reader.zoomIn")}
                  >
                    +
                  </button>
                </div>
              ) : null}
              {format.format !== "pdf" ? (
                <label className="reader-settings__check">
                  <input
                    type="checkbox"
                    checked={settings.spread}
                    onChange={(e) => update({ spread: e.target.checked })}
                  />
                  {t("media:reader.spread")}
                </label>
              ) : null}
              {format.format === "cbx" ? (
                <label className="reader-settings__check">
                  <input
                    type="checkbox"
                    checked={settings.rtl}
                    onChange={(e) => update({ rtl: e.target.checked })}
                  />
                  {t("media:reader.rtl")}
                </label>
              ) : null}
            </div>
          ) : null}
        </aside>
      ) : null}

      <footer className="reader-foot">
        <button
          type="button"
          className="player-icon reader-icon"
          onClick={() => controls?.prev()}
          aria-label={t("media:reader.previous")}
        >
          <Icon name="chevron-left" size={20} />
        </button>
        <div
          className="player-bar reader-foot__slider"
          style={{ "--played": `${share * 100}%`, "--buffered": "100%" } as CSSProperties}
        >
          <input
            type="range"
            min={0}
            max={1000}
            value={Math.round(share * 1000)}
            onChange={(e) => controls?.gotoPercent(Number(e.target.value) / 1000)}
            aria-label={t("media:reader.progress")}
            aria-valuetext={number.percent(share)}
          />
        </div>
        <span className="player-time reader-foot__where">
          {number.percent(share)}
          {left !== null ? ` · ${t("media:reader.left", { count: Math.max(1, Math.round(left)) })}` : ""}
          {info.synced ? null : (
            <span
              className="reader-foot__local"
              title={t("media:reader.notSynced", { service: info.service_name ?? "" })}
            >
              <Icon name="info" size={12} />
            </span>
          )}
        </span>
        <button
          type="button"
          className="player-icon reader-icon"
          onClick={() => controls?.next()}
          aria-label={t("media:reader.next")}
        >
          <Icon name="chevron-right" size={20} />
        </button>
      </footer>
    </div>
  );
}

export default ReaderPage;
