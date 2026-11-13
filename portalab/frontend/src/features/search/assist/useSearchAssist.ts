import { useCallback, useEffect, useRef, useState } from "react";
import { CSRF_HEADER, csrfToken } from "../../../api/client";

/**
 * ``useSearchAssist`` (spec 008 T020; R5): the AI analysis is its own request (``POST /search/assist``,
 * server-sent events) — independent of the classic results, which never wait for it. Events are kept
 * typed: ``source_ref`` (a real, permitted result) vs ``synthesis`` (interpretation).
 */
export type AssistState = "idle" | "streaming" | "done" | "unavailable" | "error";

export interface AssistSource {
  kind: string;
  id: string;
}

export interface AssistResult {
  state: AssistState;
  sources: AssistSource[];
  synthesis: string[];
}

export function parseEvents(chunk: string): Array<{ type: string; data: Record<string, unknown> }> {
  const events = [];
  for (const block of chunk.split("\n\n")) {
    let type = "message";
    let data = "";
    for (const line of block.split("\n")) {
      if (line.startsWith("event: ")) type = line.slice(7);
      else if (line.startsWith("data: ")) data += line.slice(6);
    }
    if (!data) continue;
    try {
      events.push({ type, data: JSON.parse(data) as Record<string, unknown> });
    } catch {
      // ignore a malformed frame; the stream continues
    }
  }
  return events;
}

const IDLE: AssistResult = { state: "idle", sources: [], synthesis: [] };

export function useSearchAssist() {
  const [result, setResult] = useState<AssistResult>(IDLE);
  const controller = useRef<AbortController | null>(null);
  useEffect(() => () => controller.current?.abort(), []);

  const ask = useCallback(async (query: string, refs: AssistSource[]) => {
    controller.current?.abort();
    const abort = new AbortController();
    controller.current = abort;
    setResult({ state: "streaming", sources: [], synthesis: [] });
    try {
      const headers: Record<string, string> = {
        "Content-Type": "application/json",
        Accept: "text/event-stream",
      };
      const token = csrfToken();
      if (token) headers[CSRF_HEADER] = token;
      const response = await fetch("/api/v1/search/assist", {
        method: "POST",
        credentials: "include",
        headers,
        body: JSON.stringify({ q: query, refs: refs.slice(0, 50) }),
        signal: abort.signal,
      });
      if (!response.ok || !response.body) throw new Error(`assist ${response.status}`);
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let final: AssistState = "done";
      for (;;) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const cut = buffer.lastIndexOf("\n\n");
        if (cut < 0) continue;
        const ready = buffer.slice(0, cut);
        buffer = buffer.slice(cut + 2);
        for (const event of parseEvents(ready)) {
          if (event.type === "status" && event.data.state === "unavailable") final = "unavailable";
          if (event.type === "error") final = "error";
          setResult((current) => ({
            state: current.state,
            sources:
              event.type === "source_ref"
                ? [...current.sources, { kind: String(event.data.kind), id: String(event.data.id) }]
                : current.sources,
            synthesis:
              event.type === "synthesis"
                ? [...current.synthesis, String(event.data.text ?? "")]
                : current.synthesis,
          }));
        }
      }
      setResult((current) => ({ ...current, state: final }));
    } catch (error) {
      if ((error as Error).name === "AbortError") return;
      setResult((current) => ({ ...current, state: "error" }));
    }
  }, []);

  const reset = useCallback(() => {
    controller.current?.abort();
    setResult(IDLE);
  }, []);

  return { ...result, ask, reset };
}
