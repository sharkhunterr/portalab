/**
 * Live-update client for `GET /api/v1/stream` (Server-Sent Events).
 *
 * Events are notifications to refetch (or small deltas), never the source of truth: consumers typically
 * invalidate TanStack Query keys. The browser reconnects automatically; when the connection is closed for
 * good we reconnect ourselves with exponential backoff and resume after the last received event id.
 */

export type StreamState = "connecting" | "open" | "reconnecting" | "closed";

export interface LiveEvent {
  id: string;
  topic: string;
  data: unknown;
}

export interface StreamOptions {
  url?: string;
  topics: string[];
  onEvent: (event: LiveEvent) => void;
  onStateChange?: (state: StreamState) => void;
  /** Injectable for tests. */
  createEventSource?: (url: string) => EventSource;
  initialBackoffMs?: number;
  maxBackoffMs?: number;
}

export interface StreamHandle {
  close: () => void;
}

export function backoffDelay(attempt: number, initialMs = 1000, maxMs = 30000): number {
  return Math.min(initialMs * 2 ** attempt, maxMs);
}

export function connectStream(options: StreamOptions): StreamHandle {
  const base = options.url ?? "/api/v1/stream";
  const create =
    options.createEventSource ?? ((url: string) => new EventSource(url, { withCredentials: true }));
  let source: EventSource | null = null;
  let lastEventId: string | null = null;
  let attempt = 0;
  let timer: ReturnType<typeof setTimeout> | null = null;
  let closed = false;

  const setState = (state: StreamState) => options.onStateChange?.(state);

  const open = () => {
    const url = lastEventId ? `${base}?last_event_id=${encodeURIComponent(lastEventId)}` : base;
    setState(attempt === 0 ? "connecting" : "reconnecting");
    source = create(url);
    source.onopen = () => {
      attempt = 0;
      setState("open");
    };
    source.onerror = () => {
      if (closed || !source || source.readyState !== EventSource.CLOSED) return;
      source.close();
      const delay = backoffDelay(attempt, options.initialBackoffMs, options.maxBackoffMs);
      attempt += 1;
      setState("reconnecting");
      timer = setTimeout(open, delay);
    };
    for (const topic of options.topics) {
      source.addEventListener(topic, (raw) => {
        const message = raw as MessageEvent<string>;
        lastEventId = message.lastEventId || lastEventId;
        let data: unknown = null;
        try {
          data = JSON.parse(message.data);
        } catch {
          data = null;
        }
        options.onEvent({ id: message.lastEventId, topic, data });
      });
    }
  };

  open();
  return {
    close: () => {
      closed = true;
      if (timer) clearTimeout(timer);
      source?.close();
      setState("closed");
    },
  };
}
