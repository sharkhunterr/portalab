import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback } from "react";
import { api } from "../api/client";

/**
 * Shell preferences (spec 027 R4): account-level user settings (``/me/preferences``) such as the expanded
 * navigation sections or the dismissed welcome card. They follow the user across devices; a localStorage
 * mirror gives the first paint before the server answers (and survives an unavailable backend).
 */
const KEY = ["me", "preferences", "shell"] as const;

interface PreferenceView {
  key: string;
  value: unknown;
}

function readMirror(key: string): unknown {
  try {
    const raw = window.localStorage.getItem(`portalab:${key}`);
    return raw === null ? undefined : JSON.parse(raw);
  } catch {
    return undefined;
  }
}

function writeMirror(key: string, value: unknown): void {
  try {
    window.localStorage.setItem(`portalab:${key}`, JSON.stringify(value));
  } catch {
    // storage unavailable: the server copy is the source of truth anyway
  }
}

/** The value, its setter, and whether the server's copy has arrived (to decide before showing anything). */
export function useShellPreference<T>(key: string, fallback: T): [T, (value: T) => void, boolean] {
  const client = useQueryClient();
  const query = useQuery({
    queryKey: KEY,
    staleTime: 5 * 60_000,
    retry: false,
    queryFn: async () => {
      const data = (await api.GET("/api/v1/me/preferences")).data as unknown as {
        preferences?: PreferenceView[];
      };
      return Object.fromEntries((data?.preferences ?? []).map((p) => [p.key, p.value])) as Record<
        string,
        unknown
      >;
    },
  });
  const save = useMutation({
    mutationFn: async (value: T) => {
      await api.PUT("/api/v1/me/preferences", { body: { [key]: value } as never });
    },
  });
  const stored = query.data?.[key];
  const value = (stored ?? readMirror(key) ?? fallback) as T;
  const set = useCallback(
    (next: T) => {
      writeMirror(key, next);
      client.setQueryData<Record<string, unknown>>(KEY, (old) => ({ ...(old ?? {}), [key]: next }));
      save.mutate(next);
    },
    [client, key, save],
  );
  return [value, set, query.isSuccess];
}
