import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback } from "react";
import { api } from "../api/client";
import { ME_KEY } from "../features/auth/useAuth";

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

// 032: one browser, several household members — each member's own mirror (never its master's, say, the
// welcome already seen); ``who`` is the signed-in account, unknown before ``/me`` answered
function mirrorKey(key: string, who: string | undefined): string {
  return who ? `portalab:${who}:${key}` : `portalab:${key}`;
}

function readMirror(key: string, who: string | undefined): unknown {
  if (!who) return undefined;
  try {
    const raw = window.localStorage.getItem(mirrorKey(key, who));
    return raw === null ? undefined : JSON.parse(raw);
  } catch {
    return undefined;
  }
}

function writeMirror(key: string, value: unknown, who: string | undefined): void {
  if (!who) return;
  try {
    window.localStorage.setItem(mirrorKey(key, who), JSON.stringify(value));
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
  const who = client.getQueryData<{ id?: string } | null>(ME_KEY)?.id;
  const stored = query.data?.[key];
  // the mirror paints first only: once the server answered, its copy (or the default) is the value
  const value = (stored ?? (query.isSuccess ? undefined : readMirror(key, who)) ?? fallback) as T;
  const set = useCallback(
    (next: T) => {
      writeMirror(key, next, who);
      client.setQueryData<Record<string, unknown>>(KEY, (old) => ({ ...(old ?? {}), [key]: next }));
      save.mutate(next);
    },
    [client, key, save, who],
  );
  return [value, set, query.isSuccess];
}
