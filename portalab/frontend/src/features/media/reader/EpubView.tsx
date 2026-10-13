import ePub, { type Book, type Rendition } from "epubjs";
import { useEffect, useRef } from "react";
import { readingColors } from "../../../design-system/themes/reading";
import { fileUrl } from "../books/api";
import type { ReaderSettings } from "./session";
import type { Controls, Heading, Hit, ViewProps } from "./types";

/**
 * #21: an EPUB, laid out by epub.js in frames that run **no script** (sandboxed: same origin for the layout,
 * never ``allow-scripts``) — the reader's own document allows no script but the portal's besides. Fonts, size,
 * line height, margins and colours are the member's; the position is a CFI, the share comes from the book's
 * « locations » (computed once, kept on this device).
 */
interface SpineSection {
  load(loader: (path: string) => Promise<object>): Promise<object>;
  unload(): void;
  find(query: string): { cfi: string; excerpt: string }[];
}

interface Located {
  start: { cfi: string; percentage: number; href: string };
  atEnd?: boolean;
}

const FONTS: Record<ReaderSettings["font"], string | null> = {
  publisher: null,
  serif: "Georgia, 'EB Garamond', serif",
  sans: "'Inter Variable', system-ui, sans-serif",
  dyslexic: "'Comic Neue', 'Comic Sans MS', sans-serif",
};

function styles(settings: ReaderSettings) {
  const colors = readingColors(settings.theme);
  const font = FONTS[settings.font];
  return {
    body: {
      background: `${colors.background} !important`,
      color: `${colors.color} !important`,
      "line-height": `${settings.lineHeight} !important`,
      padding: `0 ${settings.margin}rem !important`,
      ...(font ? { "font-family": `${font} !important` } : {}),
    },
    "p, li, span, div": {
      ...(font ? { "font-family": `${font} !important` } : {}),
      "line-height": `${settings.lineHeight} !important`,
    },
    a: { color: `${colors.link} !important` },
    img: { "max-width": "100% !important" },
  };
}

export function EpubView({
  ticket,
  objectId,
  format,
  resume,
  settings,
  onMoved,
  onReady,
  onFailed,
}: ViewProps) {
  const host = useRef<HTMLDivElement>(null);
  const book = useRef<Book | null>(null);
  const rendition = useRef<Rendition | null>(null);
  const settingsRef = useRef(settings);
  settingsRef.current = settings;

  // the book: fetched through the portal, opened once
  // biome-ignore lint/correctness/useExhaustiveDependencies: opened once per file; settings apply below
  useEffect(() => {
    let cancelled = false;
    const element = host.current;
    if (!element) return;
    (async () => {
      try {
        const response = await fetch(fileUrl(ticket, format.file_ref), { credentials: "include" });
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const data = await response.arrayBuffer();
        if (cancelled) return;
        const opened = ePub(data as unknown as string);
        book.current = opened;
        const view = opened.renderTo(element, {
          width: "100%",
          height: "100%",
          flow: settingsRef.current.flow === "scrolled" ? "scrolled-doc" : "paginated",
          spread: settingsRef.current.spread ? "auto" : "none",
          allowScriptedContent: false,
        } as Parameters<Book["renderTo"]>[1]);
        rendition.current = view;
        view.themes.default(styles(settingsRef.current));
        view.themes.fontSize(`${settingsRef.current.size}%`);
        view.on("relocated", (location: Located) => {
          const cfi = location.start.cfi;
          const total = opened.locations.length();
          const share = total ? opened.locations.percentageFromCfi(cfi) : location.start.percentage;
          onMoved({ position: cfi, percent: location.atEnd ? 1 : share || 0 });
        });
        view.on("keyup", (event: KeyboardEvent) => keys(event));
        let touchX: number | null = null;
        view.on("touchstart", (event: TouchEvent) => {
          touchX = event.changedTouches[0]?.screenX ?? null;
        });
        view.on("touchend", (event: TouchEvent) => {
          const end = event.changedTouches[0]?.screenX;
          if (touchX === null || end === undefined) return;
          const delta = end - touchX;
          if (Math.abs(delta) > 50) void (delta < 0 ? view.next() : view.prev());
          touchX = null;
        });
        await view.display(resume?.position || undefined);
        const navigation = await opened.loaded.navigation;
        const toc: Heading[] = [];
        const walk = (items: typeof navigation.toc, depth: number) => {
          for (const item of items) {
            toc.push({ label: item.label.trim(), target: item.href, depth });
            if (item.subitems?.length) walk(item.subitems, depth + 1);
          }
        };
        walk(navigation.toc, 0);
        const controls: Controls = {
          next: () => void view.next(),
          prev: () => void view.prev(),
          goto: (target) => void view.display(target),
          gotoPercent: (share) => {
            if (opened.locations.length()) void view.display(opened.locations.cfiFromPercentage(share));
          },
          search: async (query) => {
            const hits: Hit[] = [];
            const sections = (opened.spine as unknown as { spineItems: SpineSection[] }).spineItems;
            for (const section of sections) {
              await section.load(opened.load.bind(opened) as (path: string) => Promise<object>);
              for (const found of section.find(query))
                hits.push({ target: found.cfi, excerpt: found.excerpt });
              section.unload();
              if (hits.length >= 100) break;
            }
            return hits;
          },
        };
        onReady(toc, controls);
        // the share of the book: from its « locations », computed once and kept on this device
        const key = `portalab.reader.locations.${objectId}.${format.file_ref}`;
        let kept: string | null = null;
        try {
          kept = localStorage.getItem(key);
        } catch {
          kept = null;
        }
        if (kept) opened.locations.load(kept);
        else {
          await opened.locations.generate(1200);
          try {
            localStorage.setItem(key, opened.locations.save());
          } catch {
            // computed again next time
          }
        }
        if (!cancelled) await view.reportLocation();
      } catch {
        if (!cancelled) onFailed();
      }
    })();
    function keys(event: KeyboardEvent) {
      const view = rendition.current;
      if (!view) return;
      if (event.key === "ArrowRight" || event.key === "PageDown") void view.next();
      if (event.key === "ArrowLeft" || event.key === "PageUp") void view.prev();
    }
    window.addEventListener("keyup", keys);
    return () => {
      cancelled = true;
      window.removeEventListener("keyup", keys);
      book.current?.destroy();
      book.current = null;
      rendition.current = null;
    };
  }, [ticket, format.file_ref]);

  // the member's settings, applied as they change
  useEffect(() => {
    const view = rendition.current;
    if (!view) return;
    view.themes.default(styles(settings));
    view.themes.fontSize(`${settings.size}%`);
    view.flow(settings.flow === "scrolled" ? "scrolled-doc" : "paginated");
    view.spread(settings.spread ? "auto" : "none");
  }, [settings]);

  const colors = readingColors(settings.theme);
  return (
    <div className="reader-epub" style={{ background: colors.background }}>
      <div ref={host} className="reader-epub__pages" />
      <button
        type="button"
        className="reader-zone"
        data-side="prev"
        tabIndex={-1}
        aria-hidden="true"
        onClick={() => void rendition.current?.prev()}
      />
      <button
        type="button"
        className="reader-zone"
        data-side="next"
        tabIndex={-1}
        aria-hidden="true"
        onClick={() => void rendition.current?.next()}
      />
    </div>
  );
}
