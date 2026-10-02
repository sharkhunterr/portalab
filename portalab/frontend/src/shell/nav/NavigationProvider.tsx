import { useQuery, useQueryClient } from "@tanstack/react-query";
import { createContext, type ReactNode, useContext, useEffect } from "react";
import { api } from "../../api/client";
import { connectStream } from "../../api/stream";

/**
 * Navigation view (spec 004 T018): fetched from ``/me/navigation`` (server-filtered by rights and module
 * enablement), refetched on focus/reconnect and when the live stream announces ``navigation.changed``.
 */
export interface NavEntry {
  key: string;
  label_key: string;
  icon?: string | null;
  route?: string | null;
  existence_sensitive?: boolean;
  keywords?: string[];
}

export interface NavCommand extends NavEntry {
  kind: "navigate" | "action";
  action_id?: string | null;
  sensitivity?: "normal" | "sensitive";
  confirmation_required?: boolean;
}

export interface NavigationView {
  version: string;
  groups: Array<{ key: string; label_key: string; entries: NavEntry[] }>;
  commands: NavCommand[];
  related: Record<string, NavEntry[]>;
  crumbs: Record<string, { label_key: string; route?: string | null }>;
  degraded: boolean;
}

export const NAVIGATION_KEY = ["shell", "navigation"] as const;

/** Defensive parsing: a malformed answer degrades the navigation, it never breaks the shell. */
export function normalize(data: unknown): NavigationView {
  const raw = (data ?? {}) as Partial<NavigationView>;
  const valid = Array.isArray(raw.groups) && Array.isArray(raw.commands);
  return {
    version: typeof raw.version === "string" ? raw.version : "",
    groups: valid ? (raw.groups as NavigationView["groups"]) : [],
    commands: valid ? (raw.commands as NavigationView["commands"]) : [],
    related: raw.related && typeof raw.related === "object" ? raw.related : {},
    crumbs: raw.crumbs && typeof raw.crumbs === "object" ? raw.crumbs : {},
    degraded: !valid || Boolean(raw.degraded),
  };
}
const EMPTY: NavigationView = {
  version: "",
  groups: [],
  commands: [],
  related: {},
  crumbs: {},
  degraded: false,
};

const NavigationContext = createContext<{ view: NavigationView; loading: boolean; failed: boolean }>({
  view: EMPTY,
  loading: false,
  failed: false,
});

export function NavigationProvider({ children, live = true }: { children: ReactNode; live?: boolean }) {
  const queryClient = useQueryClient();
  const query = useQuery({
    queryKey: NAVIGATION_KEY,
    queryFn: async () => normalize((await api.GET("/api/v1/me/navigation")).data),
    refetchOnWindowFocus: true,
    refetchOnReconnect: true,
    staleTime: 30_000,
  });
  useEffect(() => {
    if (!live || typeof EventSource === "undefined") return;
    const handle = connectStream({
      topics: ["navigation.changed"],
      onEvent: () => void queryClient.invalidateQueries({ queryKey: NAVIGATION_KEY }),
    });
    return () => handle.close();
  }, [live, queryClient]);
  return (
    <NavigationContext.Provider
      value={{ view: query.data ?? EMPTY, loading: query.isPending, failed: query.isError }}
    >
      {children}
    </NavigationContext.Provider>
  );
}

export function useNavigationView() {
  return useContext(NavigationContext);
}
