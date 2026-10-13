import { useCallback, useEffect, useRef, useState } from "react";
import { reportReading, type SessionState } from "../books/api";

/**
 * #21: a reading session — where the member is (a CFI or a page), how far (0..1) and for how long they have
 * been reading. Sent to the portal (and the library) when it changes, at most every half minute, then when
 * the member leaves; a book read to its end is « finished ».
 */
export interface Place {
  position: string;
  percent: number;
}

const EVERY_MS = 30_000;
const IDLE_MS = 2 * 60_000; // no page turned for this long: the member is no longer reading

export function useReadingSession(ticket: string, format: string, fileRef: string | null) {
  const place = useRef<Place | null>(null);
  const sent = useRef<string>("");
  const seq = useRef(0);
  const seconds = useRef(0);
  const lastActive = useRef(Date.now());
  const tick = useRef(Date.now());
  const started = useRef<{ at: number; percent: number } | null>(null);
  const [current, setCurrent] = useState<Place | null>(null);

  const send = useCallback(
    (state: SessionState) => {
      const now = place.current;
      if (!now) return;
      seq.current += 1;
      void reportReading(ticket, {
        state: now.percent >= 0.995 ? "finished" : state,
        format,
        file_ref: fileRef,
        position: now.position,
        percent: now.percent,
        seconds: Math.round(seconds.current),
        seq: seq.current,
      }).catch(() => undefined);
      sent.current = now.position;
    },
    [ticket, format, fileRef],
  );

  // time spent reading: counted while the page is shown and the member turns pages
  useEffect(() => {
    const timer = window.setInterval(() => {
      const now = Date.now();
      if (document.visibilityState === "visible" && now - lastActive.current < IDLE_MS) {
        seconds.current += (now - tick.current) / 1000;
      }
      tick.current = now;
      if (place.current && place.current.position !== sent.current) send("playing");
    }, EVERY_MS);
    const hidden = () => {
      if (document.visibilityState === "hidden") send("paused");
    };
    const leave = () => send("paused");
    document.addEventListener("visibilitychange", hidden);
    window.addEventListener("pagehide", leave);
    return () => {
      window.clearInterval(timer);
      document.removeEventListener("visibilitychange", hidden);
      window.removeEventListener("pagehide", leave);
    };
  }, [send]);

  const moved = useCallback(
    (next: Place) => {
      lastActive.current = Date.now();
      const first = place.current === null;
      place.current = next;
      if (!started.current) started.current = { at: Date.now(), percent: next.percent };
      setCurrent(next);
      if (first) send("playing");
      else if (next.percent >= 0.995) send("finished");
    },
    [send],
  );

  /** The member closes the book. */
  const stop = useCallback(() => send("stopped"), [send]);

  /** Minutes left at the member's pace in this session (after a few minutes of reading). */
  const minutesLeft = (): number | null => {
    const begin = started.current;
    const now = place.current;
    if (!begin || !now || seconds.current < 120) return null;
    const done = now.percent - begin.percent;
    if (done <= 0.002) return null;
    return ((1 - now.percent) * seconds.current) / done / 60;
  };

  return { current, moved, stop, minutesLeft };
}

// --- the member's reading settings, kept on this device ------------------------------------------------
export interface ReaderSettings {
  theme: "auto" | "light" | "sepia" | "dark";
  font: "publisher" | "serif" | "sans" | "dyslexic";
  size: number; // percent
  lineHeight: number;
  margin: number; // rem
  flow: "paginated" | "scrolled";
  spread: boolean; // two pages side by side when wide enough (EPUB, comics)
  rtl: boolean; // comics read right to left (manga)
  fit: "width" | "page"; // PDF
}

export const DEFAULT_SETTINGS: ReaderSettings = {
  theme: "auto",
  font: "publisher",
  size: 100,
  lineHeight: 1.5,
  margin: 2,
  flow: "paginated",
  spread: true,
  rtl: false,
  fit: "page",
};

const SETTINGS_KEY = "portalab.reader.settings";

export function useReaderSettings() {
  const [settings, setSettings] = useState<ReaderSettings>(() => {
    try {
      return { ...DEFAULT_SETTINGS, ...JSON.parse(localStorage.getItem(SETTINGS_KEY) ?? "{}") };
    } catch {
      return DEFAULT_SETTINGS;
    }
  });
  const update = (patch: Partial<ReaderSettings>) => {
    setSettings((previous) => {
      const next = { ...previous, ...patch };
      try {
        localStorage.setItem(SETTINGS_KEY, JSON.stringify(next));
      } catch {
        // kept for this visit only
      }
      return next;
    });
  };
  return [settings, update] as const;
}

// --- bookmarks, kept on this device ---------------------------------------------------------------------
export interface Bookmark {
  position: string;
  percent: number;
  label: string;
}

export function useBookmarks(objectId: string, format: string) {
  const key = `portalab.reader.bookmarks.${objectId}.${format}`;
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
    add: (mark: Bookmark) =>
      save(
        [...marks.filter((m) => m.position !== mark.position), mark].sort((a, b) => a.percent - b.percent),
      ),
    remove: (position: string) => save(marks.filter((m) => m.position !== position)),
  };
}
