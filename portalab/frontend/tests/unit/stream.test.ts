import { afterEach, describe, expect, it, vi } from "vitest";
import { backoffDelay, connectStream, type LiveEvent, type StreamState } from "../../src/api/stream";

class FakeEventSource {
  static instances: FakeEventSource[] = [];
  readonly url: string;
  readyState = 0;
  onopen: (() => void) | null = null;
  onerror: (() => void) | null = null;
  private listeners = new Map<string, ((event: MessageEvent<string>) => void)[]>();

  constructor(url: string) {
    this.url = url;
    FakeEventSource.instances.push(this);
  }

  addEventListener(topic: string, listener: (event: MessageEvent<string>) => void) {
    this.listeners.set(topic, [...(this.listeners.get(topic) ?? []), listener]);
  }

  emit(topic: string, id: string, data: unknown) {
    for (const listener of this.listeners.get(topic) ?? []) {
      listener(new MessageEvent(topic, { data: JSON.stringify(data), lastEventId: id }));
    }
  }

  close() {
    this.readyState = 2;
  }
}

vi.stubGlobal("EventSource", Object.assign(FakeEventSource, { CONNECTING: 0, OPEN: 1, CLOSED: 2 }));

afterEach(() => {
  FakeEventSource.instances = [];
  vi.useRealTimers();
});

describe("connectStream", () => {
  it("delivers subscribed topics and reconnects with backoff, resuming after the last id", () => {
    vi.useFakeTimers();
    const events: LiveEvent[] = [];
    const states: StreamState[] = [];
    const handle = connectStream({
      topics: ["portal.ping"],
      onEvent: (event) => events.push(event),
      onStateChange: (state) => states.push(state),
      createEventSource: (url) => new FakeEventSource(url) as unknown as EventSource,
      initialBackoffMs: 100,
    });
    const first = FakeEventSource.instances[0];
    expect(first?.url).toBe("/api/v1/stream");
    first?.onopen?.();
    first?.emit("portal.ping", "41", { n: 1 });
    expect(events).toEqual([{ id: "41", topic: "portal.ping", data: { n: 1 } }]);

    first?.close();
    first?.onerror?.();
    expect(FakeEventSource.instances).toHaveLength(1);
    vi.advanceTimersByTime(100);
    const second = FakeEventSource.instances[1];
    expect(second?.url).toBe("/api/v1/stream?last_event_id=41");
    handle.close();
    expect(states).toEqual(["connecting", "open", "reconnecting", "reconnecting", "closed"]);
  });

  it("caps the backoff", () => {
    expect([0, 1, 2, 10].map((n) => backoffDelay(n, 1000, 30000))).toEqual([1000, 2000, 4000, 30000]);
  });
});
