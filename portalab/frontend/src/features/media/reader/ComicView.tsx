import { useCallback, useEffect, useRef, useState } from "react";
import { readingColors } from "../../../design-system/themes/reading";
import { useT } from "../../../i18n/hooks/useT";
import { fetchPages, pageUrl } from "../books/api";
import type { Controls, ViewProps } from "./types";

/**
 * #21: a comic book archive, page by page (images relayed by the portal): two pages side by side on a wide
 * screen when the member wants it, right to left for manga, the next pages fetched ahead. The position is
 * the page.
 */
export function ComicView({ ticket, format, resume, settings, onMoved, onReady, onFailed }: ViewProps) {
  const t = useT();
  const [pages, setPages] = useState<number[]>([]);
  const [index, setIndex] = useState(0);
  const indexRef = useRef(index);
  indexRef.current = index;
  const [wide, setWide] = useState(() => window.innerWidth > window.innerHeight * 1.1);
  const double = settings.spread && wide;
  const step = double ? 2 : 1;
  const stepRef = useRef(step);
  stepRef.current = step;

  const go = useCallback(
    (next: number) => setIndex(Math.min(Math.max(0, next), Math.max(0, pages.length - 1))),
    [pages.length],
  );

  // biome-ignore lint/correctness/useExhaustiveDependencies: opened once per file
  useEffect(() => {
    let cancelled = false;
    fetchPages(ticket, format.file_ref)
      .then((found) => {
        if (cancelled) return;
        setPages(found);
        const start = Math.max(0, found.indexOf(Number(resume?.position)));
        setIndex(start);
        const controls: Controls = {
          next: () => setIndex((i) => Math.min(found.length - 1, i + stepRef.current)),
          prev: () => setIndex((i) => Math.max(0, i - stepRef.current)),
          goto: (target) => setIndex(Math.max(0, found.indexOf(Number(target)))),
          gotoPercent: (share) => setIndex(Math.min(found.length - 1, Math.floor(share * found.length))),
        };
        onReady(
          found.map((n) => ({ label: t("media:reader.page", { number: n }), target: String(n), depth: 0 })),
          controls,
        );
      })
      .catch(() => {
        if (!cancelled) onFailed();
      });
    return () => {
      cancelled = true;
    };
  }, [ticket, format.file_ref]);

  useEffect(() => {
    const resize = () => setWide(window.innerWidth > window.innerHeight * 1.1);
    window.addEventListener("resize", resize);
    return () => window.removeEventListener("resize", resize);
  }, []);

  useEffect(() => {
    const number = pages[index];
    if (number === undefined) return;
    onMoved({ position: String(number), percent: pages.length ? (index + step) / pages.length : 0 });
    for (const ahead of pages.slice(index + 1, index + 1 + step * 2)) {
      const image = new Image();
      image.src = pageUrl(ticket, format.file_ref, ahead);
    }
  }, [index, pages, step, ticket, format.file_ref, onMoved]);

  // keys and swipes: right to left for manga
  const forward = settings.rtl ? -1 : 1;
  useEffect(() => {
    const keys = (event: KeyboardEvent) => {
      if (event.target instanceof HTMLInputElement) return;
      if (event.key === "ArrowRight") go(indexRef.current + stepRef.current * forward);
      if (event.key === "ArrowLeft") go(indexRef.current - stepRef.current * forward);
    };
    window.addEventListener("keyup", keys);
    return () => window.removeEventListener("keyup", keys);
  }, [go, forward]);
  const touch = useRef<number | null>(null);

  const shown = pages.slice(index, index + step);
  const colors = readingColors(settings.theme);
  return (
    <div
      className="reader-comic"
      data-rtl={settings.rtl || undefined}
      data-double={double || undefined}
      data-fit={settings.fit}
      style={{ background: colors.background }}
      onTouchStart={(event) => {
        touch.current = event.changedTouches[0]?.screenX ?? null;
      }}
      onTouchEnd={(event) => {
        const end = event.changedTouches[0]?.screenX;
        if (touch.current === null || end === undefined) return;
        const delta = end - touch.current;
        if (Math.abs(delta) > 50) go(indexRef.current + (delta < 0 ? step : -step) * forward);
        touch.current = null;
      }}
    >
      {shown.map((number) => (
        <img
          key={number}
          className="reader-comic__page"
          src={pageUrl(ticket, format.file_ref, number)}
          alt={t("media:reader.page", { number })}
        />
      ))}
      <button
        type="button"
        className="reader-zone"
        data-side="prev"
        tabIndex={-1}
        aria-hidden="true"
        onClick={() => go(index - step * forward)}
      />
      <button
        type="button"
        className="reader-zone"
        data-side="next"
        tabIndex={-1}
        aria-hidden="true"
        onClick={() => go(index + step * forward)}
      />
    </div>
  );
}
