import { GlobalWorkerOptions, getDocument, type PDFDocumentProxy } from "pdfjs-dist";
import workerUrl from "pdfjs-dist/build/pdf.worker.min.mjs?url";
import { useCallback, useEffect, useRef, useState } from "react";
import { readingColors } from "../../../design-system/themes/reading";
import { fileUrl } from "../books/api";
import type { Controls, Heading, Hit, ViewProps } from "./types";

GlobalWorkerOptions.workerSrc = workerUrl;

/**
 * #21: a PDF, drawn page by page by pdf.js on a canvas (never ``eval``), fitted to the page or to the width,
 * zoomable; its outline is the table of contents and its text can be searched. The position is the page.
 */
interface OutlineItem {
  title: string;
  dest: string | unknown[] | null;
  items: OutlineItem[];
}

export function PdfView({
  ticket,
  format,
  resume,
  settings,
  onMoved,
  onReady,
  onFailed,
  zoom,
}: ViewProps & { zoom: number }) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const box = useRef<HTMLDivElement>(null);
  const doc = useRef<PDFDocumentProxy | null>(null);
  const [page, setPage] = useState(() => Math.max(1, Number(resume?.position) || 1));
  const [pages, setPages] = useState(0);
  const pageRef = useRef(page);
  pageRef.current = page;

  const go = useCallback((next: number) => {
    const total = doc.current?.numPages ?? 0;
    if (!total) return;
    setPage(Math.min(total, Math.max(1, next)));
  }, []);

  // the document: fetched through the portal, opened once
  // biome-ignore lint/correctness/useExhaustiveDependencies: opened once per file
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const response = await fetch(fileUrl(ticket, format.file_ref), { credentials: "include" });
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const data = new Uint8Array(await response.arrayBuffer());
        const opened = await getDocument({ data, isEvalSupported: false }).promise;
        if (cancelled) {
          void opened.destroy();
          return;
        }
        doc.current = opened;
        setPages(opened.numPages);
        setPage((current) => Math.min(opened.numPages, current));
        const outline = ((await opened.getOutline()) ?? []) as OutlineItem[];
        const toc: Heading[] = [];
        const walk = async (items: OutlineItem[], depth: number) => {
          for (const item of items) {
            let target: number | null = null;
            try {
              const dest = typeof item.dest === "string" ? await opened.getDestination(item.dest) : item.dest;
              const ref = Array.isArray(dest) ? dest[0] : null;
              if (ref)
                target =
                  (await opened.getPageIndex(ref as Parameters<PDFDocumentProxy["getPageIndex"]>[0])) + 1;
            } catch {
              target = null;
            }
            if (target) toc.push({ label: item.title.trim(), target: String(target), depth });
            if (item.items?.length) await walk(item.items, depth + 1);
          }
        };
        await walk(outline, 0);
        const controls: Controls = {
          next: () => go(pageRef.current + 1),
          prev: () => go(pageRef.current - 1),
          goto: (target) => go(Number(target)),
          gotoPercent: (share) => go(Math.round(share * opened.numPages) || 1),
          search: async (query) => {
            const needle = query.toLowerCase();
            const hits: Hit[] = [];
            for (let n = 1; n <= opened.numPages && hits.length < 60; n += 1) {
              const text = (await (await opened.getPage(n)).getTextContent()).items
                .map((item) => ("str" in item ? item.str : ""))
                .join(" ");
              const at = text.toLowerCase().indexOf(needle);
              if (at >= 0) {
                hits.push({
                  target: String(n),
                  excerpt: `${n} — ${text.slice(Math.max(0, at - 40), at + 60)}`,
                });
              }
            }
            return hits;
          },
        };
        onReady(toc, controls);
      } catch {
        if (!cancelled) onFailed();
      }
    })();
    return () => {
      cancelled = true;
      void doc.current?.destroy();
      doc.current = null;
    };
  }, [ticket, format.file_ref]);

  // the page, drawn sharp on high-density screens
  useEffect(() => {
    const opened = doc.current;
    const target = canvas.current;
    const frame = box.current;
    if (!opened || !target || !frame || !pages) return;
    let cancelled = false;
    let task: { cancel(): void } | null = null;
    (async () => {
      const current = await opened.getPage(page);
      if (cancelled) return;
      const natural = current.getViewport({ scale: 1 });
      const fit =
        settings.fit === "width"
          ? frame.clientWidth / natural.width
          : Math.min(frame.clientWidth / natural.width, frame.clientHeight / natural.height);
      const scale = Math.max(0.2, fit * zoom);
      const ratio = window.devicePixelRatio || 1;
      const viewport = current.getViewport({ scale: scale * ratio });
      target.width = Math.floor(viewport.width);
      target.height = Math.floor(viewport.height);
      target.style.width = `${Math.floor(viewport.width / ratio)}px`;
      target.style.height = `${Math.floor(viewport.height / ratio)}px`;
      const context = target.getContext("2d");
      if (!context) return;
      const rendering = current.render({ canvasContext: context, viewport });
      task = rendering;
      try {
        await rendering.promise;
      } catch {
        // replaced by a newer drawing
      }
    })();
    onMoved({ position: String(page), percent: pages ? page / pages : 0 });
    return () => {
      cancelled = true;
      task?.cancel();
    };
  }, [page, pages, zoom, settings.fit, onMoved]);

  // keys and swipes turn pages
  useEffect(() => {
    const keys = (event: KeyboardEvent) => {
      if (event.target instanceof HTMLInputElement) return;
      if (event.key === "ArrowRight" || event.key === "PageDown") go(pageRef.current + 1);
      if (event.key === "ArrowLeft" || event.key === "PageUp") go(pageRef.current - 1);
    };
    window.addEventListener("keyup", keys);
    return () => window.removeEventListener("keyup", keys);
  }, [go]);
  const touch = useRef<number | null>(null);

  const colors = readingColors(settings.theme);
  return (
    <div
      ref={box}
      className="reader-pdf"
      data-fit={settings.fit}
      style={{ background: colors.background }}
      onTouchStart={(event) => {
        touch.current = event.changedTouches[0]?.screenX ?? null;
      }}
      onTouchEnd={(event) => {
        const end = event.changedTouches[0]?.screenX;
        if (touch.current === null || end === undefined || zoom > 1) return;
        const delta = end - touch.current;
        if (Math.abs(delta) > 50) go(pageRef.current + (delta < 0 ? 1 : -1));
        touch.current = null;
      }}
    >
      <canvas ref={canvas} className="reader-pdf__page" />
      {zoom <= 1 ? (
        <>
          <button
            type="button"
            className="reader-zone"
            data-side="prev"
            tabIndex={-1}
            aria-hidden="true"
            onClick={() => go(pageRef.current - 1)}
          />
          <button
            type="button"
            className="reader-zone"
            data-side="next"
            tabIndex={-1}
            aria-hidden="true"
            onClick={() => go(pageRef.current + 1)}
          />
        </>
      ) : null}
    </div>
  );
}
