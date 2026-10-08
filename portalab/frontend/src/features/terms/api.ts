import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../../api/client";

/** Terms of use (027): the version in force, the member's standing, the administrators' publication. */
export interface Terms {
  version: number;
  title: string;
  summary: string;
  html: string;
  requires_acceptance: boolean;
  published_at: string;
}

export interface MyTerms {
  terms: Terms | null;
  accepted_version: number | null;
  accepted_at: string | null;
  required: boolean;
}

export interface TermsAdmin {
  versions: Array<Terms & { body_md: string; acceptances: number }>;
  members_up_to_date: number;
  enabled: boolean;
}

export const MY_TERMS_KEY = ["me", "terms"] as const;
/** Fired by the API client when a call is refused because the terms in force were not accepted. */
export const TERMS_REQUIRED_EVENT = "portalab:terms-required";

export function useMyTerms(enabled = true) {
  return useQuery({
    queryKey: MY_TERMS_KEY,
    enabled,
    retry: false,
    staleTime: 5 * 60_000,
    refetchOnWindowFocus: true,
    queryFn: async () => (await api.GET("/api/v1/me/terms")).data as MyTerms,
  });
}

export function usePublicTerms(enabled = true) {
  return useQuery({
    queryKey: ["terms"],
    enabled,
    retry: false,
    staleTime: 5 * 60_000,
    queryFn: async () => ((await api.GET("/api/v1/terms")).data?.terms ?? null) as Terms | null,
  });
}

export function useAcceptTerms() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (version: number) =>
      (await api.POST("/api/v1/me/terms/accept", { body: { version } })).data as MyTerms,
    onSuccess: (data) => {
      client.setQueryData(MY_TERMS_KEY, data);
      // everything refused while the terms were pending can load now
      void client.invalidateQueries({
        predicate: (query) => query.queryKey[0] !== "me" || query.queryKey[1] !== "terms",
      });
    },
    onError: () => void client.invalidateQueries({ queryKey: MY_TERMS_KEY }), // a newer version: show it
  });
}

export function useTermsAdmin() {
  return useQuery({
    queryKey: ["admin", "terms"],
    retry: false,
    queryFn: async () => (await api.GET("/api/v1/admin/terms")).data as TermsAdmin,
  });
}

export function usePublishTerms() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (body: {
      title: string;
      summary: string;
      body_md: string;
      requires_acceptance: boolean;
    }) => (await api.POST("/api/v1/admin/terms", { body })).data as Terms,
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: ["admin", "terms"] });
      void client.invalidateQueries({ queryKey: ["terms"] });
      void client.invalidateQueries({ queryKey: MY_TERMS_KEY });
    },
  });
}
