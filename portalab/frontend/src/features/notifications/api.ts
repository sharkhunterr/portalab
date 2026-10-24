import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../../api/client";
import type { components } from "../../api/generated/schema";
import { useLocaleContext } from "../../i18n/provider/I18nProvider";

/** Notifications API hooks (spec 010): the center, the unread count and the per-category preferences. */
export type NotificationItem = components["schemas"]["NotificationOut"];
export type NotificationPage = components["schemas"]["NotificationPage"];
export type Preferences = components["schemas"]["NotificationPreferencesOut"];
export type PreferencesUpdate = components["schemas"]["NotificationPreferencesIn"];

export interface CenterFilter {
  unread?: boolean;
  kind?: "notification" | "alert";
  archived?: boolean;
}

const KEY = ["notifications"] as const;
export type BulkAction = "read" | "archive" | "unarchive" | "delete";

export function useNotifications(filter: CenterFilter, enabled = true) {
  const { language } = useLocaleContext(); // issue 242: the texts in the interface's language
  return useInfiniteQuery({
    queryKey: [...KEY, "list", filter, language],
    enabled,
    initialPageParam: null as string | null,
    getNextPageParam: (last: NotificationPage) => last.next_cursor,
    queryFn: async ({ pageParam }) =>
      (
        await api.GET("/api/v1/me/notifications", {
          params: {
            query: {
              ...(pageParam ? { cursor: pageParam } : {}),
              ...(filter.kind ? { kind: filter.kind } : {}),
              unread: filter.unread ?? false,
              archived: filter.archived ?? false,
              lang: language,
            },
          },
        })
      ).data as NotificationPage,
  });
}

export function useUnreadCount(enabled = true) {
  return useQuery({
    queryKey: [...KEY, "unread"],
    enabled,
    staleTime: 30_000,
    queryFn: async () => (await api.GET("/api/v1/me/notifications/unread-count")).data?.unread ?? 0,
  });
}

/** The newest unread items (for toasts after a live ping). */
export async function fetchLatest(language?: string): Promise<NotificationItem[]> {
  const { data } = await api.GET("/api/v1/me/notifications", {
    params: { query: { unread: true, ...(language ? { lang: language } : {}) } },
  });
  return data?.items ?? [];
}

export function useNotificationActions() {
  const client = useQueryClient();
  const settle = () => client.invalidateQueries({ queryKey: KEY });
  const read = useMutation({
    mutationFn: (id: string) =>
      api.POST("/api/v1/me/notifications/{notification_id}/read", {
        params: { path: { notification_id: id } },
      }),
    onSettled: settle,
  });
  const archive = useMutation({
    mutationFn: (id: string) =>
      api.POST("/api/v1/me/notifications/{notification_id}/archive", {
        params: { path: { notification_id: id } },
      }),
    onSettled: settle,
  });
  const remove = useMutation({
    mutationFn: (id: string) =>
      api.DELETE("/api/v1/me/notifications/{notification_id}", {
        params: { path: { notification_id: id } },
      }),
    onSettled: settle,
  });
  const readAll = useMutation({
    mutationFn: () => api.POST("/api/v1/me/notifications/read-all"),
    onSettled: settle,
  });
  /** issue 112: one action on several notifications at once (the panel's selection) */
  const bulk = useMutation({
    mutationFn: (body: { ids: string[]; action: BulkAction }) =>
      api.POST("/api/v1/me/notifications/bulk", { body }),
    onSettled: settle,
  });
  return { read, archive, remove, readAll, bulk };
}

export function usePreferences() {
  return useQuery({
    queryKey: [...KEY, "preferences"],
    queryFn: async () => (await api.GET("/api/v1/me/notification-preferences")).data as Preferences,
  });
}

export function useSavePreferences() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (body: PreferencesUpdate) => {
      const result = await api.PUT("/api/v1/me/notification-preferences", { body });
      if (result.error) throw result.error;
      return result.data as Preferences;
    },
    onSuccess: (data) => client.setQueryData([...KEY, "preferences"], data),
  });
}
