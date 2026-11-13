import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../../api/client";
import type { components } from "../../api/generated/schema";
import { ApiError } from "../../state/regions";

export type Me = components["schemas"]["Me"];
export type SessionInfo = components["schemas"]["SessionInfo"];
export type MfaRequired = components["schemas"]["MfaRequired"];

export const ME_KEY = ["identity", "me"] as const;

/** The signed-in account, or `null` when the caller is anonymous (401). */
export function useMe() {
  return useQuery({
    queryKey: ME_KEY,
    queryFn: async (): Promise<Me | null> => {
      try {
        const { data } = await api.GET("/api/v1/me");
        return data ?? null;
      } catch (error) {
        if (error instanceof ApiError && error.status === 401) return null;
        throw error;
      }
    },
    // issue 305: too many requests (a page rich in pictures just before) — wait and ask again, never an error
    retry: (count, error) => error instanceof ApiError && error.status === 429 && count < 5,
    retryDelay: (count) => Math.min(1000 * 2 ** count, 10_000),
  });
}

export function useLogin() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (body: { login: string; password: string }) => {
      const { data } = await api.POST("/api/v1/auth/login", { body });
      return data as SessionInfo | MfaRequired;
    },
    onSuccess: (data) => {
      if (!isMfaRequired(data)) void queryClient.invalidateQueries({ queryKey: ME_KEY });
    },
  });
}

/** Issue 408: the password was right and the account has a second factor — no session yet. */
export function isMfaRequired(data: SessionInfo | MfaRequired | undefined): data is MfaRequired {
  return !!data && "challenge" in data;
}

/** Issue 408: the sign-in's second step — the authenticator app's code, or a recovery code. */
export function useLoginMfa() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (body: { challenge: string; code: string }) => {
      const { data } = await api.POST("/api/v1/auth/login/mfa", { body });
      return data as SessionInfo;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ME_KEY }),
  });
}

export function useLogout() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      await api.POST("/api/v1/auth/logout");
    },
    onSuccess: () => queryClient.setQueryData(ME_KEY, null),
  });
}
