import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../../api/client";

/**
 * Issue 363, issue 378: the books, audiobooks, games… asked of the team — what kinds it takes, and asking
 * for one as a film is asked for (the portal's own request: the same « My requests », queue and figures).
 * Nothing while the module is switched off: the buttons leading to it hide.
 */
export interface AskOptions {
  kinds: string[];
  known: string[]; // every kind the team could take
}

export interface AskInput {
  kind: string;
  title: string;
  creators: string[];
  year: number | null;
  details: Record<string, string>;
  ids: Record<string, string>;
  note: string | null;
  cover: string | null;
  sheet: string | null;
}

/** What may be asked of the team — ``undefined`` (and no error shown) while the module is switched off. */
export function useAskOptions() {
  return useQuery({
    queryKey: ["requests", "options"],
    retry: false,
    staleTime: 60_000,
    queryFn: async () => (await api.GET("/api/v1/requests/options")).data as unknown as AskOptions,
  });
}

/** Asking for a book, a game… — a request of the portal's, as a film's (``POST /media/requests``). */
export function useAsk() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (body: AskInput) =>
      (
        await api.POST("/api/v1/media/requests", {
          body: { ...body, idempotency_key: `ask-${body.kind}-${Date.now()}` } as never,
        })
      ).data as unknown as { id: string; title: string; state: string },
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: ["media"] });
      void client.invalidateQueries({ queryKey: ["requests"] });
    },
  });
}

export interface AskConfig {
  kinds: string[];
}

export function useSaveAskConfig() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (config: AskConfig) =>
      api.PUT("/api/v1/admin/config", {
        body: {
          changes: [{ key: "requests.config", value: config, scope: "global", scope_ref: "", unset: false }],
          reason: "requests: kinds",
        } as never,
      }),
    onSuccess: () => client.invalidateQueries({ queryKey: ["requests"] }),
  });
}
