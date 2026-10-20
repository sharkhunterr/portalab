import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, CSRF_COOKIE, CSRF_HEADER, readCookie } from "../../api/client";
import type { components } from "../../api/generated/schema";
import { ApiError } from "../../state/regions";

/** AI assistant API (spec 018): status, owner-only conversations, the streamed turn, pending actions, admin. */
export type AiStatus = components["schemas"]["AiStatusOut"];
export type AiConversation = components["schemas"]["AiConversationOut"];
export type AiConversationDetail = components["schemas"]["AiConversationDetailOut"];
export type AiAction = components["schemas"]["AiActionOut"];
export type AiConfig = components["schemas"]["AiConfigOut"];
export type AiConfigUpdate = components["schemas"]["AiConfigIn"];
export type McpServer = components["schemas"]["McpServerOut"];
export type AiModelServer = components["schemas"]["AiServerOut"];
export type AiModel = components["schemas"]["AiModelOut"];
export type McpServersUpdate = components["schemas"]["McpServersIn"];

export type SourceClass = "real" | "historical" | "knowledge";
export interface AiSource {
  n: number;
  kind: string;
  ref: string;
  title: string;
  class: SourceClass;
  as_of: string | null;
  url: string | null;
  /** issue 171: the card beside the answer — a poster of the portal's own, a short line */
  image?: string | null;
  detail?: string | null;
}
export interface AiCaveat {
  tool: string;
  state: string;
}
export interface PendingInfo {
  id: string;
  tool: string;
  summary: string;
  expires_at: string;
}
export interface TurnDone {
  content: string;
  sources: AiSource[];
  caveats: AiCaveat[];
  interpretation: boolean;
  pending_actions: string[];
}
export type TurnEvent =
  | { event: "delta"; data: { text: string } }
  | { event: "tool_call"; data: { id: string; name: string } }
  | { event: "tool_result"; data: { id: string; name: string; state: string } }
  | { event: "source"; data: AiSource }
  | { event: "pending_action"; data: PendingInfo }
  | { event: "error"; data: { code: string; reason?: string } }
  | { event: "done"; data: TurnDone };

const KEY = ["ai"] as const;

export function useAiStatus() {
  return useQuery({
    queryKey: [...KEY, "status"],
    staleTime: 60_000,
    retry: false,
    queryFn: async (): Promise<AiStatus> => {
      try {
        return (await api.GET("/api/v1/ai/status")).data as AiStatus;
      } catch {
        return { available: false, provider_state: "unavailable", auto_navigate: false, name: "" };
      }
    },
  });
}

export function useConversations(enabled: boolean) {
  return useQuery({
    queryKey: [...KEY, "conversations"],
    enabled,
    queryFn: async () => (await api.GET("/api/v1/ai/conversations")).data ?? [],
  });
}

export async function createConversation(context?: {
  route?: string;
  title?: string;
}): Promise<AiConversation> {
  const { data } = await api.POST("/api/v1/ai/conversations", { body: context ? { context } : {} });
  return data as AiConversation;
}

export async function loadConversation(id: string): Promise<AiConversationDetail> {
  const { data } = await api.GET("/api/v1/ai/conversations/{conversation_id}", {
    params: { path: { conversation_id: id } },
  });
  return data as AiConversationDetail;
}

export async function deleteConversation(id: string): Promise<void> {
  await api.DELETE("/api/v1/ai/conversations/{conversation_id}", {
    params: { path: { conversation_id: id } },
  });
}

export function parseTurnEvents(raw: string): TurnEvent[] {
  const out: TurnEvent[] = [];
  for (const block of raw.split("\n\n")) {
    const lines = block.trim().split("\n");
    const name = lines.find((l) => l.startsWith("event: "))?.slice(7);
    const data = lines.find((l) => l.startsWith("data: "))?.slice(6);
    if (name && data) out.push({ event: name, data: JSON.parse(data) } as TurnEvent);
  }
  return out;
}

/** Streams one turn; refusals before streaming (unavailable, rate, budget) throw an ``ApiError``. */
export async function streamTurn(
  conversationId: string,
  content: string,
  onEvent: (event: TurnEvent) => void,
  signal?: AbortSignal,
  context?: { route?: string; title?: string },
): Promise<void> {
  const token = readCookie(CSRF_COOKIE);
  const response = await fetch(`/api/v1/ai/conversations/${encodeURIComponent(conversationId)}/messages`, {
    method: "POST",
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      Accept: "text/event-stream",
      ...(token ? { [CSRF_HEADER]: token } : {}),
    },
    // issue 171: the page this message is asked from (a conversation goes on across pages)
    body: JSON.stringify(context?.route ? { content, context } : { content }),
    ...(signal ? { signal } : {}),
  });
  if (!response.ok || !response.body) {
    const problem = (await response.json().catch(() => ({}))) as { code?: string; detail?: string };
    throw new ApiError(response.status, problem.detail ?? response.statusText, problem.code);
  }
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const cut = buffer.lastIndexOf("\n\n");
    if (cut < 0) continue;
    for (const event of parseTurnEvents(buffer.slice(0, cut))) onEvent(event);
    buffer = buffer.slice(cut + 2);
  }
  if (buffer.trim()) for (const event of parseTurnEvents(buffer)) onEvent(event);
}

export function useAction(id: string) {
  return useQuery({
    queryKey: [...KEY, "action", id],
    queryFn: async () =>
      (await api.GET("/api/v1/ai/actions/{action_id}", { params: { path: { action_id: id } } }))
        .data as AiAction,
  });
}

export function useActionDecision(id: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (decision: "confirm" | "decline") => {
      const path = { params: { path: { action_id: id } } };
      const { data } =
        decision === "confirm"
          ? await api.POST("/api/v1/ai/actions/{action_id}/confirm", path)
          : await api.POST("/api/v1/ai/actions/{action_id}/decline", path);
      return data as AiAction;
    },
    onSuccess: (action) => client.setQueryData([...KEY, "action", id], action),
  });
}

// --- admin -------------------------------------------------------------------------------------------
export function useAiConfig() {
  return useQuery({
    queryKey: [...KEY, "admin", "config"],
    queryFn: async () => (await api.GET("/api/v1/admin/ai/config")).data as AiConfig,
  });
}

/** Issue 169: the model servers of the connected services (Ollama) — where to point the assistant. */
export function useAiServers() {
  return useQuery({
    queryKey: [...KEY, "admin", "servers"],
    staleTime: 30_000,
    queryFn: async () => ((await api.GET("/api/v1/admin/ai/servers")).data ?? []) as AiModelServer[],
  });
}

export function useAiAdmin() {
  const client = useQueryClient();
  const settle = () => client.invalidateQueries({ queryKey: KEY });
  const save = useMutation({
    mutationFn: async (body: AiConfigUpdate) => (await api.PUT("/api/v1/admin/ai/config", { body })).data,
    onSuccess: settle,
  });
  const test = useMutation({
    mutationFn: async () => (await api.POST("/api/v1/admin/ai/provider/test")).data,
  });
  const saveServers = useMutation({
    mutationFn: async (body: McpServersUpdate) =>
      (await api.PUT("/api/v1/admin/ai/mcp-servers", { body })).data,
    onSuccess: settle,
  });
  return { save, test, saveServers };
}

export function useAiUsage() {
  return useQuery({
    queryKey: [...KEY, "admin", "usage"],
    queryFn: async () => (await api.GET("/api/v1/admin/ai/usage")).data,
  });
}

export function useMcpServers() {
  return useQuery({
    queryKey: [...KEY, "admin", "mcp"],
    queryFn: async () => (await api.GET("/api/v1/admin/ai/mcp-servers")).data ?? [],
  });
}
