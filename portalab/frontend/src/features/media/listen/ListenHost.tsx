import * as DialogPrimitive from "@radix-ui/react-dialog";
import { type CSSProperties, useEffect, useMemo, useState } from "react";
import { Link, useLocation } from "react-router";
import { Icon } from "../../../design-system/components/Icon";
import { useT } from "../../../i18n/hooks/useT";
import { imageUrl } from "../api";
import { clock } from "../books/api";
import {
  chapterStep,
  closeBook,
  currentChapter,
  leaving,
  RATES,
  restore,
  SKIP_S,
  seekTo,
  setExpanded,
  setRate,
  setSleep,
  skip,
  toggle,
  useListen,
} from "./store";
import "../player/player.css";
import "./listen.css";

/**
 * #20: the audiobook player of the whole portal — a bar at the bottom while browsing, and its bigger view
 * (cover, chapters, speed, sleep timer, bookmarks). Mounted once by the shell.
 */
export function ListenHost() {
  const location = useLocation();
  const listen = useListen();
  useEffect(() => {
    restore();
    window.addEventListener("pagehide", leaving);
    return () => window.removeEventListener("pagehide", leaving);
  }, []);
  // a film starting in the portal's video player: the audiobook steps aside
  useEffect(() => {
    if (location.pathname.endsWith("/watch") && listen.playing) toggle();
  }, [location.pathname, listen.playing]);
  if (!listen.objectId) return null;
  return (
    <>
      <MiniPlayer />
      <ListenSheet />
    </>
  );
}

function Cover({ size }: { size: "small" | "large" }) {
  const listen = useListen();
  const src = imageUrl(listen.image);
  return (
    <span className="listen-cover" data-size={size}>
      {src ? <img src={src} alt="" /> : <Icon name="headphones" size={size === "large" ? 64 : 22} />}
    </span>
  );
}

function MiniPlayer() {
  const t = useT();
  const listen = useListen();
  const chapter = currentChapter(listen.position);
  const share = listen.duration ? Math.min(1, listen.position / listen.duration) : 0;
  return (
    <section className="listen-mini" aria-label={t("media:listen.player")}>
      <span className="listen-mini__progress" aria-hidden="true">
        <span style={{ inlineSize: `${share * 100}%` }} />
      </span>
      <button
        type="button"
        className="listen-mini__open"
        onClick={() => setExpanded(true)}
        aria-label={t("media:listen.expand")}
      >
        <Cover size="small" />
        <span className="listen-mini__text">
          <strong>{listen.title || listen.info?.item.title || t("media:listen.loading")}</strong>
          <small>
            {listen.status === "error"
              ? t(
                  `media:listen.error.${listen.error === "media.books_disabled" ? "disabled" : "unavailable"}`,
                )
              : chapter
                ? chapter.title
                : (listen.info?.item.author ?? "")}
          </small>
        </span>
      </button>
      <span className="listen-mini__controls">
        <button
          type="button"
          className="listen-mini__skip"
          onClick={() => skip(-SKIP_S)}
          aria-label={t("media:listen.back", { seconds: SKIP_S })}
          disabled={listen.status !== "ready"}
        >
          <Icon name="replay-10" size={20} />
        </button>
        <button
          type="button"
          className="listen-mini__play"
          onClick={toggle}
          aria-label={t(listen.playing ? "media:listen.pause" : "media:listen.play")}
          disabled={listen.status !== "ready"}
          data-buffering={listen.buffering || listen.status === "loading" || undefined}
        >
          <Icon name={listen.playing ? "pause" : "play"} size={22} />
        </button>
        <button
          type="button"
          className="listen-mini__skip"
          onClick={() => skip(SKIP_S)}
          aria-label={t("media:listen.forward", { seconds: SKIP_S })}
          disabled={listen.status !== "ready"}
        >
          <Icon name="forward-10" size={20} />
        </button>
        <span className="listen-mini__time">
          {clock(listen.position)} / {clock(listen.duration)}
        </span>
        <button
          type="button"
          className="listen-mini__close"
          onClick={closeBook}
          aria-label={t("media:listen.close")}
        >
          <Icon name="close" size={18} />
        </button>
      </span>
    </section>
  );
}

interface Bookmark {
  at: number;
  label: string;
}

function useBookmarks(objectId: string | null) {
  const key = `portalab.listen.bookmarks.${objectId}`;
  const [marks, setMarks] = useState<Bookmark[]>(() => {
    try {
      return JSON.parse(localStorage.getItem(key) ?? "[]") as Bookmark[];
    } catch {
      return [];
    }
  });
  const save = (next: Bookmark[]) => {
    setMarks(next);
    try {
      localStorage.setItem(key, JSON.stringify(next));
    } catch {
      // kept for this visit only
    }
  };
  return {
    marks,
    add: (mark: Bookmark) => save([...marks, mark].sort((a, b) => a.at - b.at)),
    remove: (at: number) => save(marks.filter((m) => m.at !== at)),
  };
}

const SLEEP = [10, 15, 30, 45, 60] as const;

/** The bigger view: a stage like the video player's — cover, chapters cut into the seek bar, round controls,
 * speed, sleep timer, bookmarks and chapters in its panel. */
function ListenSheet() {
  const t = useT();
  const listen = useListen();
  const chapters = listen.info?.item.chapters ?? [];
  const here = currentChapter(listen.position);
  const bookmarks = useBookmarks(listen.objectId);
  const [scrub, setScrub] = useState<number | null>(null);
  const [hover, setHover] = useState<{ x: number; at: number } | null>(null);
  const sleepLeft = useMemo(() => {
    if (!listen.sleep) return null;
    if ("until" in listen.sleep) return Math.max(0, (listen.sleep.until - Date.now()) / 1000);
    return null;
  }, [listen.sleep]);
  const total = listen.duration;
  const shown = scrub ?? listen.position;
  const played = total ? (shown / total) * 100 : 0;
  const pointed = hover ? (currentChapterAt(chapters, hover.at) ?? null) : null;
  return (
    <DialogPrimitive.Root open={listen.expanded} onOpenChange={setExpanded}>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Content className="listen-stage" aria-describedby={undefined}>
          <div className="player-top listen-stage__top">
            <button
              type="button"
              className="player-icon"
              onClick={() => setExpanded(false)}
              aria-label={t("media:listen.collapse")}
            >
              <Icon name="chevron-down" size={24} />
            </button>
            <DialogPrimitive.Title className="player-title">
              <strong>{listen.title || listen.info?.item.title || t("media:listen.player")}</strong>
              {listen.info?.item.author ? <span>{listen.info.item.author}</span> : null}
            </DialogPrimitive.Title>
            {listen.objectId ? (
              <Link
                className="player-pill"
                to={`/media/${listen.objectId}`}
                onClick={() => setExpanded(false)}
              >
                {t("media:listen.page")}
              </Link>
            ) : null}
          </div>

          <div className="listen-stage__body">
            <div className="listen-stage__art">
              <Cover size="large" />
              {here ? <p className="listen-stage__chapter">{here.title}</p> : null}
              {listen.info?.item.narrator ? (
                <p className="listen-stage__muted">
                  {t("media:listen.narrator", { name: listen.info.item.narrator })}
                </p>
              ) : null}
              {listen.info && !listen.info.synced ? (
                <p className="listen-stage__muted">
                  <Icon name="info" size={14} />
                  {t("media:listen.notSynced", { service: listen.info.service_name ?? "" })}
                </p>
              ) : null}
            </div>

            <aside className="listen-stage__panel" aria-label={t("media:listen.chapters")}>
              {bookmarks.marks.length ? (
                <section>
                  <h3>{t("media:listen.bookmarks")}</h3>
                  <ul>
                    {bookmarks.marks.map((mark) => (
                      <li key={mark.at}>
                        <button type="button" className="player-row" onClick={() => seekTo(mark.at)}>
                          <span>{mark.label}</span>
                          <small>{clock(mark.at)}</small>
                        </button>
                        <button
                          type="button"
                          className="player-icon"
                          onClick={() => bookmarks.remove(mark.at)}
                          aria-label={t("media:listen.removeBookmark")}
                        >
                          <Icon name="close" size={14} />
                        </button>
                      </li>
                    ))}
                  </ul>
                </section>
              ) : null}
              {chapters.length ? (
                <section>
                  <h3>{t("media:listen.chapters")}</h3>
                  <ol>
                    {chapters.map((chapter) => (
                      <li key={chapter.index} data-current={chapter === here || undefined}>
                        <button type="button" className="player-row" onClick={() => seekTo(chapter.start_s)}>
                          <span>{chapter.title}</span>
                          <small>{clock(chapter.end_s - chapter.start_s)}</small>
                        </button>
                      </li>
                    ))}
                  </ol>
                </section>
              ) : null}
            </aside>
          </div>

          <div className="player-bottom listen-stage__bottom">
            <div
              className="player-bar"
              style={{ "--played": `${played}%`, "--buffered": `${played}%` } as CSSProperties}
              onPointerMove={(event) => {
                const box = event.currentTarget.getBoundingClientRect();
                const fraction = Math.min(1, Math.max(0, (event.clientX - box.left) / box.width));
                setHover({ x: fraction * 100, at: fraction * total });
              }}
              onPointerLeave={() => setHover(null)}
            >
              {total > 0
                ? chapters
                    .slice(1)
                    .map((chapter) => (
                      <span
                        key={chapter.index}
                        className="player-mark"
                        data-kind="chapter"
                        aria-hidden="true"
                        style={{ left: `${(chapter.start_s / total) * 100}%` }}
                      />
                    ))
                : null}
              {pointed && total > 0 ? (
                <span
                  className="player-chapter-hover"
                  aria-hidden="true"
                  style={{
                    left: `${(pointed.start_s / total) * 100}%`,
                    width: `${((pointed.end_s - pointed.start_s) / total) * 100}%`,
                  }}
                />
              ) : null}
              {hover ? (
                <span className="player-hover" style={{ left: `${hover.x}%` }} aria-hidden="true">
                  {pointed ? <small>{pointed.title}</small> : null}
                  <span>{clock(hover.at)}</span>
                </span>
              ) : null}
              <input
                type="range"
                min={0}
                max={Math.max(1, Math.round(total))}
                step={1}
                value={Math.round(shown)}
                aria-label={t("media:listen.position")}
                aria-valuetext={`${clock(shown)} / ${clock(total)}`}
                onChange={(e) => setScrub(Number(e.target.value))}
                onPointerUp={() => {
                  if (scrub !== null) seekTo(scrub);
                  setScrub(null);
                }}
                onKeyUp={() => {
                  if (scrub !== null) seekTo(scrub);
                  setScrub(null);
                }}
              />
            </div>
            <div className="player-controls">
              <button
                type="button"
                className="player-icon player-main"
                onClick={toggle}
                aria-label={t(listen.playing ? "media:listen.pause" : "media:listen.play")}
              >
                <Icon name={listen.playing ? "pause" : "play"} size={28} />
              </button>
              <button
                type="button"
                className="player-icon"
                onClick={() => chapterStep(-1)}
                aria-label={t("media:listen.previousChapter")}
              >
                <Icon name="skip-back" size={22} />
              </button>
              <button
                type="button"
                className="player-icon"
                onClick={() => skip(-SKIP_S)}
                aria-label={t("media:listen.back", { seconds: SKIP_S })}
              >
                <Icon name="replay-10" size={22} />
              </button>
              <button
                type="button"
                className="player-icon"
                onClick={() => skip(SKIP_S)}
                aria-label={t("media:listen.forward", { seconds: SKIP_S })}
              >
                <Icon name="forward-10" size={22} />
              </button>
              <button
                type="button"
                className="player-icon"
                onClick={() => chapterStep(1)}
                aria-label={t("media:listen.nextChapter")}
              >
                <Icon name="skip-forward" size={22} />
              </button>
              <span className="player-time">
                {clock(shown)} / {clock(total)}
              </span>
              <span className="player-spacer" />
              <label className="listen-stage__option">
                <Icon name="gauge" size={16} />
                <span className="visually-hidden">{t("media:listen.speed")}</span>
                <select
                  value={listen.rate}
                  onChange={(e) => setRate(Number(e.target.value))}
                  aria-label={t("media:listen.speed")}
                >
                  {RATES.map((rate) => (
                    <option key={rate} value={rate}>
                      {rate}×
                    </option>
                  ))}
                </select>
              </label>
              <label className="listen-stage__option" data-on={listen.sleep ? "true" : undefined}>
                <Icon name="moon" size={16} />
                <select
                  aria-label={t("media:listen.sleep")}
                  value={listen.sleep === null ? "" : "chapterEnd" in listen.sleep ? "chapter" : "custom"}
                  onChange={(e) => {
                    const value = e.target.value;
                    setSleep(value === "" ? null : value === "chapter" ? "chapter" : Number(value));
                  }}
                >
                  <option value="">{t("media:listen.sleepOff")}</option>
                  {SLEEP.map((minutes) => (
                    <option key={minutes} value={minutes}>
                      {t("media:listen.sleepMinutes", { count: minutes })}
                    </option>
                  ))}
                  <option value="chapter">{t("media:listen.sleepChapter")}</option>
                  {listen.sleep && "until" in listen.sleep ? (
                    <option value="custom" disabled>
                      {t("media:listen.sleepLeft", { time: clock(sleepLeft ?? 0) })}
                    </option>
                  ) : null}
                </select>
              </label>
              <button
                type="button"
                className="player-icon"
                onClick={() =>
                  bookmarks.add({
                    at: Math.round(listen.position),
                    label: here?.title ?? clock(listen.position),
                  })
                }
                aria-label={t("media:listen.addBookmark")}
                title={t("media:listen.addBookmark")}
              >
                <Icon name="bookmark" size={20} />
              </button>
            </div>
          </div>
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  );
}

function currentChapterAt(
  chapters: { start_s: number; end_s: number; title: string; index: number }[],
  at: number,
) {
  let found: (typeof chapters)[number] | null = null;
  for (const chapter of chapters) if (at >= chapter.start_s) found = chapter;
  return found;
}
