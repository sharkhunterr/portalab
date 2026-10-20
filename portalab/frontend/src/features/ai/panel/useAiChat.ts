import { useCallback, useRef, useState } from "react";
import { ApiError } from "../../../state/regions";
import {
  type AiCaveat,
  type AiSource,
  createConversation,
  loadConversation,
  type PendingInfo,
  streamTurn,
} from "../api";

/** One rendered message: streamed text first, replaced by the sanitized final answer on ``done``. */
export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  sources: AiSource[];
  caveats: AiCaveat[];
  interpretation: boolean;
  tools: string[];
  pending: string[];
  streaming: boolean;
  error?: string;
}

const empty = (role: ChatMessage["role"], content = ""): ChatMessage => ({
  role,
  content,
  sources: [],
  caveats: [],
  interpretation: false,
  tools: [],
  pending: [],
  streaming: false,
});

export function useAiChat(context?: { route?: string; title?: string }) {
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const abort = useRef<AbortController | null>(null);

  const patchLast = useCallback((update: (message: ChatMessage) => ChatMessage) => {
    setMessages((current) => [
      ...current.slice(0, -1),
      update(current[current.length - 1] ?? empty("assistant")),
    ]);
  }, []);

  const send = useCallback(
    async (text: string, options?: { fresh?: boolean }) => {
      const content = text.trim();
      if (!content || busy) return;
      setBusy(true);
      setError(null);
      try {
        // issue 171: a question asked from the search bar (or a page) starts a conversation of its own
        const fresh = Boolean(options?.fresh);
        const id = (fresh ? null : conversationId) ?? (await createConversation(context)).id;
        setConversationId(id);
        setMessages((current) => [
          ...(fresh ? [] : current),
          empty("user", content),
          { ...empty("assistant"), streaming: true },
        ]);
        abort.current = new AbortController();
        await streamTurn(
          id,
          content,
          (event) => {
            switch (event.event) {
              case "delta":
                patchLast((m) => ({ ...m, content: m.content + event.data.text }));
                break;
              case "tool_call":
                patchLast((m) => ({ ...m, tools: [...m.tools, event.data.name] }));
                break;
              case "pending_action":
                patchLast((m) => ({ ...m, pending: [...m.pending, (event.data as PendingInfo).id] }));
                break;
              case "error":
                setError(event.data.code);
                patchLast((m) => ({ ...m, streaming: false, error: event.data.code }));
                break;
              case "done":
                patchLast((m) => ({
                  ...m,
                  content: event.data.content,
                  sources: event.data.sources,
                  caveats: event.data.caveats,
                  interpretation: event.data.interpretation,
                  pending: event.data.pending_actions,
                  streaming: false,
                }));
                break;
              default:
                break;
            }
          },
          abort.current.signal,
          context,
        );
      } catch (caught) {
        if ((caught as Error).name !== "AbortError") {
          const code = caught instanceof ApiError ? (caught.code ?? "generic") : "generic";
          setError(code);
          setMessages((current) =>
            current.filter((m) => !(m.role === "assistant" && m.streaming && !m.content)),
          );
        }
      } finally {
        patchLast((m) => (m.streaming ? { ...m, streaming: false } : m));
        setBusy(false);
      }
    },
    [busy, conversationId, context, patchLast],
  );

  const stop = useCallback(() => abort.current?.abort(), []);

  const open = useCallback(async (id: string) => {
    const detail = await loadConversation(id);
    setConversationId(id);
    setError(null);
    setMessages(
      detail.messages
        .filter((m) => m.role === "user" || m.role === "assistant")
        .map((m) => {
          const blocks = m.blocks as Partial<{
            sources: AiSource[];
            caveats: AiCaveat[];
            interpretation: boolean;
            pending_actions: string[];
            error: string | null;
          }>;
          return {
            ...empty(m.role as ChatMessage["role"], m.content),
            sources: blocks.sources ?? [],
            caveats: blocks.caveats ?? [],
            interpretation: m.role === "assistant" && Boolean(blocks.interpretation),
            pending: blocks.pending_actions ?? [],
            ...(blocks.error ? { error: "ai.unavailable" } : {}),
          };
        }),
    );
  }, []);

  const reset = useCallback(() => {
    setConversationId(null);
    setMessages([]);
    setError(null);
  }, []);

  return { conversationId, messages, busy, error, send, stop, open, reset };
}
