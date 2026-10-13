import type { BookFormat, ReadingPosition } from "../books/api";
import type { Place, ReaderSettings } from "./session";

/** #21: what the reader's chrome asks of a view (EPUB, PDF, comic), whatever the format. */
export interface Heading {
  label: string;
  target: string; // a CFI or href (EPUB), a page number (PDF)
  depth: number;
}

export interface Hit {
  target: string;
  excerpt: string;
}

export interface Controls {
  next(): void;
  prev(): void;
  goto(target: string): void;
  gotoPercent(share: number): void;
  search?: (query: string) => Promise<Hit[]>;
}

export interface ViewProps {
  ticket: string;
  objectId: string;
  format: BookFormat;
  resume: ReadingPosition | undefined;
  settings: ReaderSettings;
  onMoved(place: Place): void;
  onReady(toc: Heading[], controls: Controls): void;
  onFailed(): void;
}
