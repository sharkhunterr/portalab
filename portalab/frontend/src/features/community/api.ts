import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../../api/client";
import type { components } from "../../api/generated/schema";
import { ApiError } from "../../state/regions";

export type CommunityMemberPage = components["schemas"]["CommunityMemberPage"];
export type CommunityProfile = components["schemas"]["CommunityProfileOut"];
export type CommunitySection = components["schemas"]["CommunitySectionOut"];
export type CommunityFeedPage = components["schemas"]["CommunityFeedPage"];
export type CommunityShelf = components["schemas"]["CommunityShelfOut"];
export type CommunityShelfInfo = components["schemas"]["CommunityShelfInfo"];
export type CommunityEvent = components["schemas"]["CommunityEventOut"];
export type CommunityEventInput = components["schemas"]["EventInput"];

const KEY = ["community"] as const;

export function useMembers(query: string) {
  return useInfiniteQuery({
    queryKey: [...KEY, "members", query],
    initialPageParam: null as string | null,
    getNextPageParam: (last: CommunityMemberPage) => last.next_cursor,
    queryFn: async ({ pageParam }) =>
      (
        await api.GET("/api/v1/community/members", {
          params: { query: { ...(query ? { q: query } : {}), ...(pageParam ? { cursor: pageParam } : {}) } },
        })
      ).data as CommunityMemberPage,
  });
}

export function useProfile(memberId: string) {
  return useQuery({
    queryKey: [...KEY, "profile", memberId],
    retry: false,
    queryFn: async () => {
      try {
        const { data } = await api.GET("/api/v1/community/members/{member_id}", {
          params: { path: { member_id: memberId } },
        });
        return (data ?? null) as CommunityProfile | null;
      } catch (error) {
        if (error instanceof ApiError && error.status === 404) return null; // absent or not visible: same answer
        throw error;
      }
    },
  });
}

export function useFeed() {
  return useInfiniteQuery({
    queryKey: [...KEY, "feed"],
    initialPageParam: null as string | null,
    getNextPageParam: (last: CommunityFeedPage) => last.next_cursor,
    queryFn: async ({ pageParam }) =>
      (
        await api.GET("/api/v1/community/feed", {
          params: { query: pageParam ? { cursor: pageParam } : {} },
        })
      ).data as CommunityFeedPage,
  });
}

export function useShelves() {
  return useQuery({
    queryKey: [...KEY, "shelves"],
    queryFn: async () => ((await api.GET("/api/v1/community/discovery")).data ?? []) as CommunityShelfInfo[],
  });
}

export function useShelf(shelf: string) {
  return useQuery({
    queryKey: [...KEY, "shelf", shelf],
    queryFn: async () =>
      (await api.GET("/api/v1/community/discovery/{shelf}", { params: { path: { shelf } } }))
        .data as CommunityShelf,
  });
}

export function useCommunityEvents() {
  return useQuery({
    queryKey: [...KEY, "events"],
    queryFn: async () => ((await api.GET("/api/v1/community/events")).data ?? []) as CommunityEvent[],
  });
}

export function useEventAdmin() {
  const client = useQueryClient();
  const refresh = () => client.invalidateQueries({ queryKey: [...KEY, "events"] });
  const save = useMutation({
    mutationFn: async ({ id, body }: { id: string | null; body: CommunityEventInput }) => {
      const result = id
        ? await api.PATCH("/api/v1/community/events/{event_id}", { params: { path: { event_id: id } }, body })
        : await api.POST("/api/v1/community/events", { body });
      if (!result.data) throw new Error("event not saved");
      return result.data as CommunityEvent;
    },
    onSuccess: refresh,
  });
  const cancel = useMutation({
    mutationFn: async (id: string) =>
      (await api.POST("/api/v1/community/events/{event_id}/cancel", { params: { path: { event_id: id } } }))
        .data as CommunityEvent,
    onSuccess: refresh,
  });
  return { save, cancel };
}
